# 文件路径: models/auto_trade_task.py
from sqlalchemy import Column, Integer, String, DECIMAL, DateTime, ForeignKey, UniqueConstraint
from datetime import datetime
from .base import Base

class AutoTradeTask(Base):
    __tablename__ = 'auto_trade_task'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    api_key_id = Column(Integer, ForeignKey('api_key.id', ondelete='CASCADE'), nullable=False)
    platform = Column(String(20), nullable=False, default='bybit')
    symbol = Column(String(20), nullable=False)
    category = Column(String(10), default='spot')
    status = Column(String(20), default='holding')   # holding, selling, finished
    position_qty = Column(DECIMAL(20,8), default=0)
    avg_price = Column(DECIMAL(20,8), default=0)
    last_trade_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, onupdate=datetime.now)

    __table_args__ = (UniqueConstraint('user_id', 'platform', 'api_key_id', 'symbol', name='uix_user_platform_key_symbol'),)