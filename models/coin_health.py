# 文件路径: models/coin_health.py
from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from .base import Base

class CoinHealth(Base):
    __tablename__ = 'coin_health'
    id = Column(Integer, primary_key=True)
    key_id = Column(Integer, nullable=False)
    symbol = Column(String(20), nullable=False)
    health_score = Column(Float, default=60.0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)