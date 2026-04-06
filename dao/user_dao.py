# 文件路径: dao/user_dao.py
from models.user import User
from utils.db import Session

class UserDAO:
    @staticmethod
    def get_by_username(username):
        session = Session()
        try:
            return session.query(User).filter_by(username=username).first()
        finally:
            session.close()

    @staticmethod
    def get_by_id(user_id):
        session = Session()
        try:
            return session.query(User).get(user_id)
        finally:
            session.close()

    @staticmethod
    def get_all():
        session = Session()
        try:
            return session.query(User).all()
        finally:
            session.close()

    @staticmethod
    def create(user):
        session = Session()
        try:
            session.add(user)
            session.commit()
            return user
        finally:
            session.close()

    @staticmethod
    def update(user):
        session = Session()
        try:
            session.merge(user)
            session.commit()
        finally:
            session.close()

    @staticmethod
    def delete(user_id):
        session = Session()
        try:
            user = session.query(User).get(user_id)
            if user:
                session.delete(user)
                session.commit()
        finally:
            session.close()