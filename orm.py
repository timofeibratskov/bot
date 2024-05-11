from database import async_engine, Base, async_session_factory
from sqlalchemy import text, insert, select
from modls import metadata_obj, Users


async def create_table():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def insert_data(user_tg_id, user_value):
    async with async_session_factory() as session:
        user = Users(id=user_tg_id, value=user_value)
        session.add(user)
        await session.flush()
        await session.commit()


async def update_value(user_id, new_user_value):
    async with async_session_factory() as session:
        user = await session.get(Users, user_id)
        user.value = new_user_value
        await session.flush()
        await session.commit()


async def select_values():
    async with async_session_factory() as session:
        query = select(Users)
        result = await session.execute(query)
        users = result.scalars().all()
        return f'{users=}'


async def get_user(user_id):
    async with async_session_factory() as session:
        user = await session.get(Users, user_id)
        return user
