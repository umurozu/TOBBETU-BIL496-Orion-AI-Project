"""
User ORM Model — SQLAlchemy Declarative Model
HLD Module: Model Layer — Data Access

Maps to the 'users' table in the PostgreSQL database.
This model represents the persistent user entity, separate from
the domain-level dataclass (app.model.user.User) which handles
in-memory business logic.

Table Schema (expected from teammate's migration):
    users:
        id          : SERIAL PRIMARY KEY
        email       : VARCHAR UNIQUE NOT NULL
        username    : VARCHAR UNIQUE NOT NULL
        hashed_pw   : VARCHAR NOT NULL
        is_active   : BOOLEAN DEFAULT TRUE
        created_at  : TIMESTAMP DEFAULT NOW()
        updated_at  : TIMESTAMP DEFAULT NOW()
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
)

from app.config.database import Base


class UserDB(Base):
    """
    ORM model for the 'users' table.

    If your teammate's table uses a different name (e.g. 'user', 'app_users'),
    update __tablename__ accordingly.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column("hashed_pw", String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    consent_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<UserDB(id={self.id}, email='{self.email}', username='{self.username}')>"
