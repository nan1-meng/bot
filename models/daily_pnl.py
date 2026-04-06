# 文件路径: models/daily_pnl.py
from sqlalchemy import Column, Integer, String, Float, Date
from .base import Base

class DailyPnl(Base):
    __tablename__ = 'daily_pnl'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)
    total_pnl = Column(Float, nullable=False)
    total_fee = Column(Float, nullable=False)
    trade_count = Column(Integer, nullable=False)
    win_count = Column(Integer, nullable=False)
    lose_count = Column(Integer, nullable=False)