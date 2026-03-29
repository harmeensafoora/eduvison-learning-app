from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from sqlalchemy.pool import AsyncAdaptedQueuePool, StaticPool
from .config import DATABASE_URL

# PostgreSQL connection pooling: pool_size=20, max_overflow=10
# For SQLite, use single-queue pool
engine_kwargs = {
    "echo": False,
    "future": True,
}

if "sqlite" in DATABASE_URL:
    # SQLite doesn't support pool_size/max_overflow
    engine_kwargs["poolclass"] = StaticPool
else:
    engine_kwargs["pool_size"] = 20
    engine_kwargs["max_overflow"] = 10
    engine_kwargs["poolclass"] = AsyncAdaptedQueuePool

engine = create_async_engine(DATABASE_URL, **engine_kwargs)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    async with engine.begin() as conn:
        from . import db_models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)

        # Dev-time schema sync for SQLite: `create_all()` won't alter existing tables.
        if "sqlite" in str(engine.url):
            # users table (hashed_password/email verification)
            try:
                result = await conn.execute(text("PRAGMA table_info(users)"))
                existing_cols = {row._mapping.get("name") for row in result.fetchall()}
                if "hashed_password" not in existing_cols:
                    await conn.execute(text("ALTER TABLE users ADD COLUMN hashed_password TEXT"))
                if "email_verified_at" not in existing_cols:
                    await conn.execute(text("ALTER TABLE users ADD COLUMN email_verified_at DATETIME"))
            except Exception:
                pass

            try:
                result = await conn.execute(text("PRAGMA table_info(topic_progress)"))
                existing_cols = {row._mapping.get("name") for row in result.fetchall()}
                if "needs_simplification" not in existing_cols:
                    await conn.execute(text("ALTER TABLE topic_progress ADD COLUMN needs_simplification BOOLEAN DEFAULT 0"))
                if "current_difficulty" not in existing_cols:
                    await conn.execute(text("ALTER TABLE topic_progress ADD COLUMN current_difficulty TEXT DEFAULT 'medium'"))
                if "updated_at" not in existing_cols:
                    await conn.execute(text("ALTER TABLE topic_progress ADD COLUMN updated_at DATETIME"))
            except Exception:
                # If the table doesn't exist yet (fresh DB) or PRAGMA fails, ignore.
                pass
