# 文件路径: dao/auto_trade_dao.py
from models.auto_trade_task import AutoTradeTask
from utils.db import Session

class AutoTradeDAO:
    @staticmethod
    def get_task(user_id, api_key_id, symbol):
        session = Session()
        try:
            return session.query(AutoTradeTask).filter_by(
                user_id=user_id,
                api_key_id=api_key_id,
                symbol=symbol
            ).first()
        finally:
            session.close()

    @staticmethod
    def get_all_tasks(user_id, api_key_id=None):
        session = Session()
        try:
            query = session.query(AutoTradeTask).filter_by(user_id=user_id)
            if api_key_id:
                query = query.filter_by(api_key_id=api_key_id)
            return query.all()
        finally:
            session.close()

    @staticmethod
    def create(task):
        session = Session()
        try:
            session.add(task)
            session.commit()
            return task
        finally:
            session.close()

    @staticmethod
    def update(task):
        session = Session()
        try:
            session.merge(task)
            session.commit()
        finally:
            session.close()

    @staticmethod
    def delete(task_id):
        session = Session()
        try:
            task = session.query(AutoTradeTask).get(task_id)
            if task:
                session.delete(task)
                session.commit()
        finally:
            session.close()