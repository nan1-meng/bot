from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class ApiKey(Base):
    __tablename__ = 'api_key'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    platform = Column(String(20), nullable=False, default='bybit')
    key_name = Column(String(50), nullable=False)
    api_key = Column(String(255), nullable=False)
    api_secret = Column(String(255), nullable=False)
    is_valid = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    user = relationship('User', backref='api_keys')
    __table_args__ = (UniqueConstraint('user_id', 'platform', 'key_name', name='uix_user_platform_keyname'),)
