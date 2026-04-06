# 文件路径: database/coin_health.py
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class CoinHealth(Base):
    __tablename__ = 'coin_health'
    id = Column(Integer, primary_key=True)
    key_id = Column(Integer, nullable=False)
    symbol = Column(String(20), nullable=False)
    health_score = Column(Float, default=60.0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class CoinHealthDAO:
    @staticmethod
    def get(key_id: int, symbol: str, session):
        return session.query(CoinHealth).filter_by(key_id=key_id, symbol=symbol).first()

    @staticmethod
    def upsert(key_id: int, symbol: str, health_score: float, session):
        record = session.query(CoinHealth).filter_by(key_id=key_id, symbol=symbol).first()
        if record:
            record.health_score = health_score
        else:
            record = CoinHealth(key_id=key_id, symbol=symbol, health_score=health_score)
            session.add(record)
        session.commit()