# 文件路径: models/bot_session.py
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey
from datetime import datetime
from .base import Base

class BotSession(Base):
    __tablename__ = 'bot_session'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    key_id = Column(Integer, ForeignKey('api_key.id'), nullable=False)
    symbol = Column(String(20), nullable=False)
    bot_mode = Column(String(20), nullable=False)
    sub_mode = Column(String(20))
    config = Column(JSON)
    start_time = Column(DateTime, default=datetime.now)
    end_time = Column(DateTime)
    initial_balance = Column(Float)
    final_balance = Column(Float)
    pnl = Column(Float)
    pnl_percent = Column(Float)
    status = Column(String(20), default='running')  # running, stopped, crashed