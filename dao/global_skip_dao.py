# 文件路径: dao/global_skip_dao.py
from models.global_skip import GlobalSkip
from utils.db import Session

class GlobalSkipDAO:
    @staticmethod
    def is_skipped(user_id, api_key_id, symbol):
        session = Session()
        try:
            return session.query(GlobalSkip).filter_by(
                user_id=user_id, api_key_id=api_key_id, symbol=symbol
            ).first() is not None
        finally:
            session.close()

    @staticmethod
    def add_skip(user_id, api_key_id, symbol, reason=""):
        if len(reason) > 500:
            reason = reason[:497] + "..."
        session = Session()
        try:
            existing = session.query(GlobalSkip).filter_by(
                user_id=user_id, api_key_id=api_key_id, symbol=symbol
            ).first()
            if not existing:
                skip = GlobalSkip(
                    user_id=user_id,
                    api_key_id=api_key_id,
                    symbol=symbol,
                    reason=reason
                )
                session.add(skip)
                session.commit()
        finally:
            session.close()

    @staticmethod
    def clear_skipped(user_id, api_key_id):
        session = Session()
        try:
            session.query(GlobalSkip).filter_by(user_id=user_id, api_key_id=api_key_id).delete()
            session.commit()
        finally:
            session.close()

