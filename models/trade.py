# 文件路径: models/trade.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Boolean
from datetime import datetime
from .base import Base

class Trade(Base):
    __tablename__ = 'trade'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    key_id = Column(Integer, ForeignKey('api_key.id'), nullable=False)
    platform = Column(String(20), nullable=True)
    bot_mode = Column(String(20), nullable=False)
    sub_mode = Column(String(20))
    symbol = Column(String(20), nullable=False)
    side = Column(String(4), nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    amount_usdt = Column(Float, nullable=False)
    fee = Column(Float, nullable=False)
    order_id = Column(String(100))
    source_trade_id = Column(String(100), nullable=True)
    is_manual = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.now)
    pnl = Column(Float, nullable=True)
    exit_reason = Column(String(50), nullable=True)
    hold_seconds = Column(Integer, nullable=True)
    entry_score = Column(Float, nullable=True)
    market_state = Column(String(20), nullable=True)
    entry_kline = Column(JSON, nullable=True)
    exit_kline = Column(JSON, nullable=True)
    highest_price = Column(Float, nullable=True)
    highest_time = Column(DateTime, nullable=True)
    lowest_price = Column(Float, nullable=True)
    lowest_time = Column(DateTime, nullable=True)
    add_records = Column(JSON, nullable=True)
