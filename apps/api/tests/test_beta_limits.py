import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.beta_usage import BetaUsage
from app.services.beta_limits import reserve_paid_units


class BetaLimitsTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_limit_is_durable_and_character_deletion_cannot_reset_it(self):
        with patch("app.services.beta_limits.settings.beta_max_image_outputs", 2):
            with self.sessions() as db:
                reserve_paid_units(db, "image", 2)
                db.commit()
            with self.sessions() as db:
                self.assertEqual(db.get(BetaUsage, "image").used, 2)
                with self.assertRaises(HTTPException) as raised:
                    reserve_paid_units(db, "image", 1)
                self.assertEqual(raised.exception.status_code, 429)

    def test_zero_disables_paid_requests_and_rollback_releases_reservation(self):
        with patch("app.services.beta_limits.settings.beta_max_video_requests", 0):
            with self.sessions() as db, self.assertRaises(HTTPException):
                reserve_paid_units(db, "video", 1)
        with patch("app.services.beta_limits.settings.beta_max_video_requests", 1):
            with self.sessions() as db:
                reserve_paid_units(db, "video", 1)
                db.rollback()
            with self.sessions() as db:
                reserve_paid_units(db, "video", 1)
                db.commit()
            with self.sessions() as db:
                self.assertEqual(db.get(BetaUsage, "video").used, 1)

    def test_negative_cap_leaves_site_wide_usage_unrestricted(self):
        with patch("app.services.beta_limits.settings.beta_max_image_outputs", -1):
            with self.sessions() as db:
                reserve_paid_units(db, "image", 100)
                db.commit()
            with self.sessions() as db:
                self.assertIsNone(db.get(BetaUsage, "image"))


if __name__ == "__main__":
    unittest.main()
