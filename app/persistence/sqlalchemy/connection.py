from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

async_engine = create_async_engine(
    url=settings.DATABASE_URL,
    future=True,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_POOL_OVERFLOW,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_pre_ping=True,
    echo=False,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    async_engine, autoflush=False, expire_on_commit=False, class_=AsyncSession
)
