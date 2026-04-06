# 文件路径: models/learning_report.py
from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime
from .base import Base

class LearningReport(Base):
    __tablename__ = 'learning_report'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    report_type = Column(String(50), nullable=False)  # loss_analysis, parameter_adjustment, win_analysis
    symbol = Column(String(20), nullable=True)
    content = Column(Text, nullable=False)  # JSON 字符串
    created_at = Column(DateTime, default=datetime.now)