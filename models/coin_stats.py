# 文件路径: models/coin_stats.py
from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from .base import Base

class CoinStats(Base):
    __tablename__ = 'coin_stats'
    id = Column(Integer, primary_key=True)
    key_id = Column(Integer, nullable=False)
    symbol = Column(String(20), nullable=False)
    total_trades = Column(Integer, default=0)
    win_trades = Column(Integer, default=0)
    total_profit = Column(Float, default=0.0)
    total_loss = Column(Float, default=0.0)
    avg_win = Column(Float, nullable=True)
    avg_loss = Column(Float, nullable=True)
    win_rate = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )