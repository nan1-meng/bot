# 文件路径: dao/symbol_config_dao.py
from models.symbol_config import SymbolConfig
from utils.db import Session
import logging

logger = logging.getLogger(__name__)

class SymbolConfigDAO:
    @staticmethod
    def get_by_api_key(api_key_id):
        session = Session()
        try:
            return session.query(SymbolConfig).filter_by(api_key_id=api_key_id, is_active=True).all()
        finally:
            session.close()

    @staticmethod
    def get_by_id(config_id):
        session = Session()
        try:
            return session.query(SymbolConfig).get(config_id)
        finally:
            session.close()

    @staticmethod
    def create(config):
        session = Session()
        try:
            session.add(config)
            session.commit()
            return config.id
        finally:
            session.close()

    @staticmethod
    def update(config):
        session = Session()
        try:
            session.merge(config)
            session.commit()
        finally:
            session.close()

    @staticmethod
    def delete(config_id):
        session = Session()
        try:
            config = session.query(SymbolConfig).get(config_id)
            if config:
                session.delete(config)
                session.commit()
        except Exception as e:
            logger.error(f"删除配置 {config_id} 失败: {e}")
        finally:
            session.close()

    @staticmethod
    def get_by_user_key_symbol(user_id, api_key_id, symbol, mode):
        session = Session()
        try:
            return session.query(SymbolConfig).filter_by(user_id=user_id, api_key_id=api_key_id, symbol=symbol, mode=mode).first()
        finally:
            session.close()

    @staticmethod
    def update_position(config_id, avg_price, quantity):
        session = Session()
        try:
            config = session.query(SymbolConfig).get(config_id)
            if config:
                config.avg_price = avg_price
                config.quantity = quantity
                config.last_position_value = (avg_price or 0) * (quantity or 0)
                session.commit()
        finally:
            session.close()

    @staticmethod
    def clear_position(config_id):
        session = Session()
        try:
            config = session.query(SymbolConfig).get(config_id)
            if config:
                config.avg_price = None
                config.quantity = None
                config.last_position_value = 0.0
                session.commit()
        finally:
            session.close()
