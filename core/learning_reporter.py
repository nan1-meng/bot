# 文件路径: core/learning_reporter.py
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from utils.db import Session
from models.learning_report import LearningReport
import logging

logger = logging.getLogger(__name__)

class LearningReporter:
    """
    记录学习报告（参数调整、亏损分析等），供用户查看
    """
    def __init__(self, user_id: int):
        self.user_id = user_id
        self._lock = threading.RLock()

    def record_loss(self, trade, error_type: str):
        """记录亏损交易分析"""
        report = {
            'type': 'loss_analysis',
            'trade_id': trade.id if hasattr(trade, 'id') else None,
            'symbol': trade.symbol,
            'pnl': trade.pnl,
            'exit_reason': trade.exit_reason,
            'market_state': trade.market_state,
            'error_type': error_type,
            'timestamp': datetime.now(),
            'details': {
                'price': trade.price,
                'quantity': trade.quantity,
                'hold_seconds': trade.hold_seconds,
                'entry_score': trade.entry_score,
            }
        }
        self._save_report(report)

    def record_win(self, trade):
        """记录盈利交易（可选）"""
        report = {
            'type': 'win_analysis',
            'trade_id': trade.id if hasattr(trade, 'id') else None,
            'symbol': trade.symbol,
            'pnl': trade.pnl,
            'exit_reason': trade.exit_reason,
            'timestamp': datetime.now(),
        }
        self._save_report(report)

    def record_adjustment(self, symbol: str, param_name: str, old_value: Any, new_value: Any, reason: str):
        """记录参数调整"""
        report = {
            'type': 'parameter_adjustment',
            'symbol': symbol,
            'param_name': param_name,
            'old_value': old_value,
            'new_value': new_value,
            'reason': reason,
            'timestamp': datetime.now(),
        }
        self._save_report(report)

    def _save_report(self, report: Dict):
        session = Session()
        try:
            record = LearningReport(
                user_id=self.user_id,
                report_type=report['type'],
                symbol=report.get('symbol'),
                content=json.dumps(report, default=str),
                created_at=report['timestamp']
            )
            session.add(record)
            session.commit()
        except Exception as e:
            logger.error(f"保存学习报告失败: {e}")
            session.rollback()
        finally:
            session.close()

    def get_recent_losses(self, symbol: str, limit: int = 3) -> List[Dict]:
        """获取该币种最近的亏损交易报告"""
        session = Session()
        try:
            records = session.query(LearningReport).filter(
                LearningReport.user_id == self.user_id,
                LearningReport.symbol == symbol,
                LearningReport.report_type == 'loss_analysis'
            ).order_by(LearningReport.created_at.desc()).limit(limit).all()
            return [json.loads(r.content) for r in records]
        finally:
            session.close()

    def get_recent_adjustments(self, limit: int = 50) -> List[Dict]:
        """获取最近的参数调整记录"""
        session = Session()
        try:
            records = session.query(LearningReport).filter(
                LearningReport.user_id == self.user_id,
                LearningReport.report_type == 'parameter_adjustment'
            ).order_by(LearningReport.created_at.desc()).limit(limit).all()
            return [json.loads(r.content) for r in records]
        finally:
            session.close()

    def cleanup_old_reports(self, days: int = 30):
        """清理过期报告，表不存在时静默处理"""
        session = Session()
        try:
            cutoff = datetime.now() - timedelta(days=days)
            session.query(LearningReport).filter(
                LearningReport.user_id == self.user_id,
                LearningReport.created_at < cutoff
            ).delete()
            session.commit()
        except Exception as e:
            # 表可能尚未创建，仅记录警告
            logger.warning(f"清理学习报告失败（可能表未创建）: {e}")
            session.rollback()
        finally:
            session.close()

    def record_snapshot(self, symbol: str = None, params: Dict = None):
        """记录策略快照（每小时一次）"""
        report = {
            'type': 'strategy_snapshot',
            'symbol': symbol,
            'params': params,
            'timestamp': datetime.now(),
        }
        self._save_report(report)