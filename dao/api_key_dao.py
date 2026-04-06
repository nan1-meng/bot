# 文件路径: dao/api_key_dao.py
from models.api_key import ApiKey
from utils.db import Session

class ApiKeyDAO:
    @staticmethod
    def get_by_id(key_id):
        session = Session()
        try:
            return session.query(ApiKey).get(key_id)
        finally:
            session.close()

    @staticmethod
    def get_by_user(user_id):
        session = Session()
        try:
            return session.query(ApiKey).filter_by(user_id=user_id).all()
        finally:
            session.close()

    @staticmethod
    def create(api_key):
        session = Session()
        try:
            session.add(api_key)
            session.flush()
            key_id = api_key.id
            session.commit()
            return key_id
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def update(api_key):
        session = Session()
        try:
            session.merge(api_key)
            session.commit()
        finally:
            session.close()

    @staticmethod
    def delete(key_id):
        session = Session()
        try:
            key = session.query(ApiKey).get(key_id)
            if key:
                session.delete(key)
                session.commit()
        finally:
            session.close()