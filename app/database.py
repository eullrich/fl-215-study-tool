from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import DATABASE_URL, DATA_DIR


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
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
