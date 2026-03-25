from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import DATABASE_URL, DATA_DIR


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _needs_schema_reset(conn) -> bool:
    """Check if existing DB has stale schema (old time-based columns)."""
    def _check(sync_conn):
        insp = inspect(sync_conn)
        if "card_schedules" not in insp.get_table_names():
            return False
        columns = {c["name"] for c in insp.get_columns("card_schedules")}
        return "next_review_at" in columns or "review_after_position" not in columns
    return await conn.run_sync(_check)


async def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        if await _needs_schema_reset(conn):
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Auto-seed if DB is empty
    from app.models.content import Chapter
    async with async_session() as session:
        result = await session.execute(select(Chapter).limit(1))
        if result.scalar_one_or_none() is None:
            from data.seed_content import seed
            await seed()


async def get_db():
    async with async_session() as session:
        yield session
