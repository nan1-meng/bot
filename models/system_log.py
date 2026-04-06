# 文件路径: models/system_log.py
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from datetime import datetime
from .base import Base

class SystemLog(Base):
    __tablename__ = 'system_log'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    key_id = Column(Integer, ForeignKey('api_key.id', ondelete='CASCADE'), nullable=True)  # 可为空，全局日志
    level = Column(String(20), nullable=False)  # INFO, WARNING, ERROR
    category = Column(String(50))  # 系统、交易、风控等
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)