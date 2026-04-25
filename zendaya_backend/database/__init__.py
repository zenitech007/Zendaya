"""Database Module - SQLAlchemy Models and Database Connection"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, ForeignKey
from typing import AsyncGenerator
import logging

logger = logging.getLogger(__name__)

# Create the SQLAlchemy base class for declarative models
Base = declarative_base()

# Create async engine using aiosqlite
engine = create_async_engine(
    "sqlite+aiosqlite:///./zendaya.db",  # Use aiosqlite driver
    echo=False,
    future=True
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get a database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {str(e)}")
            raise
        finally:
            await session.close()

async def init_db() -> None:
    """Initialize the database, creating all tables."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise

# Import models after Base is defined to avoid circular imports
class APIKey(Base):
    __tablename__ = 'api_keys'
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship("User", back_populates="api_keys")

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    api_keys = relationship("APIKey", back_populates="user")

__all__ = [
    "Base",
    "get_db",
    "init_db",
    "User",
    "APIKey",
    "AsyncSession"
]
