# 文件路径: models/strategy_params.py
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from datetime import datetime
from .base import Base

class StrategyParams(Base):
    __tablename__ = 'strategy_params'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    key_id = Column(Integer, nullable=True)
    symbol = Column(String(20), nullable=True)
    param_name = Column(String(50), nullable=False)
    param_value = Column(Text, nullable=False)  # 改为 Text 类型
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )