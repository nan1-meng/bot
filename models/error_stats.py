# 文件路径: models/error_stats.py
from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from .base import Base

class ErrorStats(Base):
    __tablename__ = 'error_stats'
    id = Column(Integer, primary_key=True)
    key_id = Column(Integer, nullable=False)
    symbol = Column(String(20), nullable=False)
    error_type = Column(String(50), nullable=False)
    count = Column(Integer, default=0)
    total_loss = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )