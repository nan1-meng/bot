# 文件路径: models/symbol_config.py
from sqlalchemy import Column, Integer, String, JSON, Boolean, DateTime, ForeignKey, UniqueConstraint, Float
from datetime import datetime
from .base import Base

class SymbolConfig(Base):
    __tablename__ = 'symbol_config'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    api_key_id = Column(Integer, ForeignKey('api_key.id', ondelete='CASCADE'), nullable=False)
    platform = Column(String(20), nullable=False, default='bybit')
    symbol = Column(String(20), nullable=False)
    category = Column(String(10), default='spot')
    mode = Column(String(20), nullable=False)
    config_json = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, onupdate=datetime.now)
    manual_avg_price = Column(Float, nullable=True)
    avg_price = Column(Float, nullable=True)
    quantity = Column(Float, nullable=True)
    source_type = Column(String(20), default='manual')
    is_pinned = Column(Boolean, default=False)
    auto_resume = Column(Boolean, default=True)
    is_hidden = Column(Boolean, default=False)
    runtime_state = Column(String(20), nullable=True)
    last_position_value = Column(Float, nullable=True)
    __table_args__ = (UniqueConstraint('user_id', 'platform', 'api_key_id', 'symbol', 'mode', name='uix_user_platform_key_symbol_mode'),)
