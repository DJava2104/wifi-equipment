from sqlalchemy import Column, Integer, ForeignKey
from db.base import Base

class Likes(Base):
    __tablename__ = "likes"

    id_user = Column(Integer, ForeignKey("users.id_user"), nullable=False, primary_key=True)
    id_routers = Column(Integer, ForeignKey("routers.id_routers"), nullable=False, primary_key=True)