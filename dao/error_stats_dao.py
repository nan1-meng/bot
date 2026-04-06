# 文件路径: dao/error_stats_dao.py
from models.error_stats import ErrorStats
from utils.db import Session

class ErrorStatsDAO:
    @staticmethod
    def increment_error(key_id: int, symbol: str, error_type: str, loss: float):
        session = Session()
        try:
            record = session.query(ErrorStats).filter_by(
                key_id=key_id, symbol=symbol, error_type=error_type
            ).first()
            if record:
                record.count += 1
                record.total_loss += loss
            else:
                record = ErrorStats(
                    key_id=key_id, symbol=symbol, error_type=error_type,
                    count=1, total_loss=loss
                )
                session.add(record)
            session.commit()
        finally:
            session.close()

    @staticmethod
    def get_stats(key_id: int, symbol: str = None, error_type: str = None):
        session = Session()
        try:
            query = session.query(ErrorStats).filter_by(key_id=key_id)
            if symbol:
                query = query.filter_by(symbol=symbol)
            if error_type:
                query = query.filter_by(error_type=error_type)
            return query.all()
        finally:
            session.close()