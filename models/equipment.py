from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, func
from db.base import Base

class Equipment(Base):
    __tablename__ = "equipment"

    id_equipment = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    standard = Column(String(50), nullable=True)
    max_speed = Column(Integer, nullable=True)
    band = Column(String(20), nullable=True)
    antennas = Column(String(30), nullable=True)
    image_url = Column(String(255), nullable=True)
    video_url = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    date_created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    creator = Column(String(50), nullable=False)
    date_formed = Column(TIMESTAMP, nullable=True)
    status = Column(String(20), nullable=False, server_default="черновик")