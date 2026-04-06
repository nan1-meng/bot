# 文件路径: dao/system_log_dao.py
from models.system_log import SystemLog
from utils.db import Session

class SystemLogDAO:
    @staticmethod
    def add(user_id, key_id, level, category, message):
        session = Session()
        try:
            log = SystemLog(
                user_id=user_id,
                key_id=key_id,
                level=level,
                category=category,
                message=message
            )
            session.add(log)
            session.commit()
        finally:
            session.close()

    @staticmethod
    def get_logs(user_id, key_id=None, level=None, limit=500):
        session = Session()
        try:
            query = session.query(SystemLog).filter_by(user_id=user_id)
            if key_id:
                query = query.filter_by(key_id=key_id)
            if level:
                query = query.filter_by(level=level)
            return query.order_by(SystemLog.created_at.desc()).limit(limit).all()
        finally:
            session.close()