from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.media_asset import MediaAsset
from app.models.user import UserConsent
from app.services.account_limits import reserve_account_units
from app.services.image_storage import character_storage_key


def test_registration_sessions_and_data_isolation():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with patch("app.main.SessionLocal", sessions):
            first, second, stranger = TestClient(app), TestClient(app), TestClient(app)
            assert stranger.get("/characters").status_code == 401
            assert first.post("/auth/register", json={"email": "first@example.com", "password": "a secure password", "display_name": "First", "privacy_consent": False}).status_code == 422
            assert first.post("/auth/register", json={"email": "FIRST@example.com", "password": "a secure password", "display_name": "First", "privacy_consent": True}).status_code == 201
            assert second.post("/auth/register", json={"email": "second@example.com", "password": "another password", "display_name": "Second", "privacy_consent": True}).status_code == 201
            assert first.post("/auth/register", json={"email": "first@example.com", "password": "a secure password", "display_name": "First", "privacy_consent": True}).status_code == 409
            with sessions() as db:
                assert db.query(UserConsent).count() == 2
            created = first.post("/characters", json={"name": "Alice"})
            assert created.status_code == 200, created.text
            character_id = created.json()["id"]
            assert len(first.get("/characters").json()) == 1
            assert second.get("/characters").json() == []
            assert second.get(f"/characters/{character_id}").status_code == 404
            assert second.get(f"/chat/{character_id}").status_code == 404
            assert second.get(f"/media/{character_id}").status_code == 404
            assert second.patch("/users/profile", json={"character_id": character_id, "city": "Moscow"}).status_code == 404
            assert second.post("/memories", json={"character_id": character_id, "memory_type": "user_fact", "content": "private"}).status_code == 404
            with sessions() as db:
                db.add(MediaAsset(character_id=character_id, media_type="image", url="/media-files/private/photo.png"))
                db.commit()
            assert len(first.get(f"/media/{character_id}").json()) == 1
            assert second.get(f"/media/{character_id}").status_code == 404
            memory = first.post("/memories", json={"character_id": character_id, "memory_type": "user_fact", "content": "private"})
            assert memory.status_code == 200
            assert second.patch(f"/memories/{memory.json()['id']}", json={"content": "stolen"}).status_code == 404
            assert second.post(f"/video/{character_id}", json={}).status_code == 404
            with TemporaryDirectory() as directory:
                key = character_storage_key(character_id)
                stored = Path(directory) / key
                stored.mkdir()
                (stored / "private.png").write_bytes(b"private media")
                mounted = next(route.app for route in app.routes if route.path == "/media-files")
                with patch.object(mounted, "all_directories", [Path(directory)]):
                    assert first.get(f"/media-files/{key}/private.png").status_code == 200
                    assert second.get(f"/media-files/{key}/private.png").status_code == 404
            assert first.post("/auth/logout").status_code == 200
            assert first.get("/characters").status_code == 401
            assert first.post("/auth/login", json={"email": "first@example.com", "password": "wrong password"}).status_code == 401
            assert first.post("/auth/login", json={"email": "first@example.com", "password": "a secure password"}).status_code == 200
            assert len(first.get("/characters").json()) == 1
            first.close(); second.close(); stranger.close()
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_account_allowance_survives_character_deletion():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    try:
        from app.models.user import User
        from fastapi import HTTPException
        with sessions() as db:
            user = User(email="quota@example.com", display_name="Quota")
            db.add(user); db.commit()
            for _ in range(10):
                reserve_account_units(db, user.id, "images_count")
                db.commit()
            try:
                reserve_account_units(db, user.id, "images_count")
                assert False, "Eleventh image must be rejected"
            except HTTPException as exc:
                assert exc.status_code == 429
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
