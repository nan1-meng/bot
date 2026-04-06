# 文件路径: database/trade_analysis.py
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class TradeAnalysis(Base):
    __tablename__ = 'trade_analysis'
    id = Column(Integer, primary_key=True)
    key_id = Column(Integer, nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(4))
    pnl_usdt = Column(Float)
    pnl_pct = Column(Float)
    exit_reason = Column(String(50))
    hold_seconds = Column(Integer)
    market_state = Column(String(20))
    created_at = Column(DateTime, default=datetime.now)

class TradeAnalysisDAO:
    @staticmethod
    def insert(key_id, symbol, side, pnl_usdt, pnl_pct, exit_reason, hold_seconds, market_state, session):
        record = TradeAnalysis(
            key_id=key_id, symbol=symbol, side=side, pnl_usdt=pnl_usdt, pnl_pct=pnl_pct,
            exit_reason=exit_reason, hold_seconds=hold_seconds, market_state=market_state
        )
        session.add(record)
        session.commit()

    @staticmethod
    def get_recent_losses(key_id: int, days: int, session):
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=days)
        results = session.query(TradeAnalysis).filter(
            TradeAnalysis.key_id == key_id,
            TradeAnalysis.pnl_usdt < 0,
            TradeAnalysis.created_at >= cutoff
        ).all()
        return [{'symbol': r.symbol, 'exit_reason': r.exit_reason} for r in results]

    @staticmethod
    def get_add_position_fail_count(key_id: int, symbol: str, session):
        """补仓失败次数：补仓后仍然亏损的交易次数"""
        # 简化：统计该币种卖出时 exit_reason 为 'add_position_loss' 的次数
        count = session.query(TradeAnalysis).filter(
            TradeAnalysis.key_id == key_id,
            TradeAnalysis.symbol == symbol,
            TradeAnalysis.exit_reason == 'add_position_loss'
        ).count()
        return count