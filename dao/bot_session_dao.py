# 文件路径: dao/bot_session_dao.py
from models.bot_session import BotSession
from utils.db import Session

class BotSessionDAO:
    @staticmethod
    def create(session_obj):
        session = Session()
        try:
            session.add(session_obj)
            session.commit()
            return session_obj.id
        finally:
            session.close()

    @staticmethod
    def get_by_id(session_id):
        session = Session()
        try:
            return session.query(BotSession).get(session_id)
        finally:
            session.close()

    @staticmethod
    def update(session_obj):
        session = Session()
        try:
            session.merge(session_obj)
            session.commit()
        finally:
            session.close()