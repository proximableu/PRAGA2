"""Async database engine and session factory configuration."""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config import settings

# Construct asynchronous execution engine with connection pooling.
# `expire_on_commit=False` is critical in async contexts to prevent
# lazy-loading blocks on committed objects [2].
engine = create_async_engine(
    settings.POSTGRES_DSN,
    echo=False,
    pool_size=20,
    max_overflow=10
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)