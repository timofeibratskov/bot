from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from config import URL
from sqlalchemy.orm import DeclarativeBase

async_engine = create_async_engine(url=URL)

async_engine_factory = async_sessionmaker(async_engine)
async_session_factory = async_sessionmaker(async_engine)


class Base(DeclarativeBase):
    pass
