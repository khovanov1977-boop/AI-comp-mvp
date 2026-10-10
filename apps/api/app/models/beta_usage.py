from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BetaUsage(Base):
    """Durable paid-request counter; character deletion must not reset the cap."""

    __tablename__ = "beta_usage"

    kind: Mapped[str] = mapped_column(String, primary_key=True)
    used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
