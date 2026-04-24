"""
Database Configuration — Async SQLAlchemy Engine
HLD Module: Core Configuration — Data Access Layer

Provides:
    - Async SQLAlchemy engine bound to PostgreSQL (Docker)
    - Scoped async session factory for request-level transactions
    - Base declarative model for ORM entities
    - get_db() dependency for FastAPI route injection
"""

import logging
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


# ---- Engine & Session Factory (lazy-initialized) ----
_engine = None
_async_session_factory = None


def _get_engine():
    """Returns the singleton async engine, creating it on first call."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DB_ECHO,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_pre_ping=True,  # detect stale connections
        )
        logger.info("Database engine created → %s", settings.DATABASE_URL.split("@")[-1])
    return _engine


def _get_session_factory():
    """Returns the singleton async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


# ---- FastAPI Dependency ----
async def get_db() -> AsyncSession:
    """
    Yields a scoped async database session per request.

    Usage in routes:
        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---- Lifecycle Helpers (called from main.py lifespan) ----
async def init_db():
    """
    Creates all tables that don't exist yet.
    Implements retry logic to handle DB startup latency (LLD §1.2.5).
    """
    max_retries = 5
    retry_delay = 2
    
    for attempt in range(1, max_retries + 1):
        try:
            engine = _get_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables verified / created.")
            return
        except Exception as e:
            if attempt == max_retries:
                logger.critical(f"Failed to connect to database after {max_retries} attempts: {e}")
                raise
            logger.warning(f"Database connection attempt {attempt} failed. Retrying in {retry_delay}s...")
            await asyncio.sleep(retry_delay)


async def close_db():
    """
    Disposes the engine connection pool.
    Called during application shutdown.
    """
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
        logger.info("Database engine disposed.")
