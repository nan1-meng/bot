# 文件路径: dao/trade_dao.py
from models.trade import Trade
from utils.db import Session

class TradeDAO:
    @staticmethod
    def create(trade):
        session = Session()
        try:
            session.add(trade)
            session.commit()
            return trade.id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def get_by_user(user_id, limit=100):
        session = Session()
        try:
            return session.query(Trade).filter_by(user_id=user_id).order_by(Trade.timestamp.desc()).limit(limit).all()
        finally:
            session.close()

    @staticmethod
    def delete(trade_id):
        session = Session()
        try:
            trade = session.query(Trade).get(trade_id)
            if trade:
                session.delete(trade)
                session.commit()
        finally:
            session.close()

    @staticmethod
    def get_by_order_id(order_id):
        session = Session()
        try:
            return session.query(Trade).filter_by(order_id=order_id).first()
        finally:
            session.close()
