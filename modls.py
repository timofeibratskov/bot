from sqlalchemy import MetaData
from database import Base
from sqlalchemy.orm import Mapped, mapped_column


class Users(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str]


metadata_obj = MetaData()
