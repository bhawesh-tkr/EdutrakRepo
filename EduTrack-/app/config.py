from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "sqlite+aiosqlite:///./edutrack.db"

# Create async engine for SQLite (disable same-thread enforcement for async tasks)
engine = create_async_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Session factory for generating clean database instances per requests
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    """Declarative base configuration for SQLAlchemy models."""
    pass

# FastAPI Dependency Injection provider for Async DB Sessions
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
