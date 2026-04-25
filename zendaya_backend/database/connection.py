"""
Database Connection and Session Management - Supabase PostgreSQL (Async)
"""

import asyncio
import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.exc import OperationalError
from zendaya_backend.core.config import settings

# -----------------------------------------------------
# Logger
# -----------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# -----------------------------------------------------
# Determine database URL (Supabase preferred)
# -----------------------------------------------------
database_url = settings.supabase_db_url or settings.database_url

if not database_url:
    raise ValueError("❌ No database URL found in environment variables.")

# Normalize driver string
if database_url.startswith("postgresql://"):
    if "asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    db_type = "Supabase PostgreSQL"
elif database_url.startswith("sqlite:///"):
    if "aiosqlite" not in database_url:
        database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    db_type = "SQLite (local)"
else:
    raise ValueError(f"❌ Unsupported database URL scheme: {database_url}")

# -----------------------------------------------------
# Create async SQLAlchemy engine
# -----------------------------------------------------
try:
    engine = create_async_engine(
        database_url,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=10 if "postgresql" in database_url else None,
        max_overflow=20 if "postgresql" in database_url else None,
    )
    logger.info(f"✅ Initialized SQLAlchemy engine for {db_type}")
except Exception as e:
    logger.exception(f"❌ Failed to create async engine: {e}")
    raise

# -----------------------------------------------------
# Session factory
# -----------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# -----------------------------------------------------
# Dependency - for FastAPI endpoints
# -----------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provides an async database session to routes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# -----------------------------------------------------
# Database initialization (for local SQLite use only)
# -----------------------------------------------------
async def init_db():
    """Create tables locally. Supabase manages schema via migrations."""
    from zendaya_backend.database.models import Base

    if "sqlite" in database_url:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Local SQLite tables initialized")
    else:
        logger.info("ℹ️ Skipping table creation; Supabase manages migrations.")

# -----------------------------------------------------
# Test connection
# -----------------------------------------------------
async def test_connection() -> bool:
    """Verify database connection."""
    try:
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        logger.info("✅ Database connection test successful")
        return True
    except OperationalError as oe:
        logger.error(f"❌ OperationalError connecting to database: {oe}")
    except Exception as e:
        logger.error(f"❌ Database connection test failed: {e}")
    return False


# -----------------------------------------------------
# Manual test runner (if run directly)
# -----------------------------------------------------
if __name__ == "__main__":
    async def _main():
        logger.info("🔍 Testing database connectivity...")
        await test_connection()

    asyncio.run(_main())
