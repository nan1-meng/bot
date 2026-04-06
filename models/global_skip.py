# 文件路径: models/global_skip.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from datetime import datetime
from .base import Base

class GlobalSkip(Base):
    __tablename__ = 'global_skip'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    api_key_id = Column(Integer, ForeignKey('api_key.id', ondelete='CASCADE'), nullable=False)
    symbol = Column(String(20), nullable=False)
    reason = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (UniqueConstraint('user_id', 'api_key_id', 'symbol', name='uix_user_key_symbol'),)