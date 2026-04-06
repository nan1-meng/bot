# 文件路径: dao/coin_health_dao.py
from models.coin_health import CoinHealth
from utils.db import Session

class CoinHealthDAO:
    @staticmethod
    def get(key_id: int, symbol: str, session=None):
        close_session = False
        if session is None:
            session = Session()
            close_session = True
        try:
            return session.query(CoinHealth).filter_by(key_id=key_id, symbol=symbol).first()
        finally:
            if close_session:
                session.close()

    @staticmethod
    def get_all_by_key(key_id: int, session=None):
        close_session = False
        if session is None:
            session = Session()
            close_session = True
        try:
            return session.query(CoinHealth).filter_by(key_id=key_id).all()
        finally:
            if close_session:
                session.close()

    @staticmethod
    def upsert(key_id: int, symbol: str, health_score: float, session=None):
        close_session = False
        if session is None:
            session = Session()
            close_session = True
        try:
            record = session.query(CoinHealth).filter_by(key_id=key_id, symbol=symbol).first()
            if record:
                record.health_score = health_score
            else:
                record = CoinHealth(key_id=key_id, symbol=symbol, health_score=health_score)
                session.add(record)
            session.commit()
        finally:
            if close_session:
                session.close()

    @staticmethod
    def get_all_by_key(key_id: int, session=None):
        close_session = False
        if session is None:
            session = Session()
            close_session = True
        try:
            return session.query(CoinHealth).filter_by(key_id=key_id).all()
        finally:
            if close_session:
                session.close()

    @staticmethod
    def delete_by_key(key_id: int, session=None):
        close_session = False
        if session is None:
            session = Session()
            close_session = True
        try:
            session.query(CoinHealth).filter_by(key_id=key_id).delete()
            session.commit()
        finally:
            if close_session:
                session.close()