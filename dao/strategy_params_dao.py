# ============================================================
# 文件: dao/strategy_params_dao.py
# ============================================================

import json
from models.strategy_params import StrategyParams
from utils.db import Session
import logging

logger = logging.getLogger(__name__)


class StrategyParamsDAO:
    @staticmethod
    def get_param(user_id: int, param_name: str, symbol: str = None, key_id: int = None):
        session = Session()
        try:
            query = session.query(StrategyParams).filter(
                StrategyParams.user_id == user_id,
                StrategyParams.param_name == param_name
            )
            if symbol is None:
                query = query.filter(StrategyParams.symbol.is_(None))
            else:
                query = query.filter_by(symbol=symbol)
            record = query.first()
            if not record and key_id:
                query = session.query(StrategyParams).filter(
                    StrategyParams.key_id == key_id,
                    StrategyParams.param_name == param_name
                )
                if symbol is None:
                    query = query.filter(StrategyParams.symbol.is_(None))
                else:
                    query = query.filter_by(symbol=symbol)
                record = query.first()
            if record:
                if param_name == "add_position_ratios":
                    try:
                        return json.loads(record.param_value)
                    except:
                        if ',' in record.param_value:
                            return [float(x.strip()) for x in record.param_value.split(',')]
                        return [0.5, 0.3, 0.2]
                return record.param_value
            return None
        finally:
            session.close()

    @staticmethod
    def set_param(user_id: int, param_name: str, param_value, symbol: str = None, key_id: int = None):
        session = Session()
        try:
            if param_name == "add_position_ratios" and isinstance(param_value, list):
                param_value = json.dumps(param_value)
            query = session.query(StrategyParams).filter(
                StrategyParams.user_id == user_id,
                StrategyParams.param_name == param_name
            )
            if symbol is None:
                query = query.filter(StrategyParams.symbol.is_(None))
            else:
                query = query.filter_by(symbol=symbol)
            record = query.first()
            if record:
                record.param_value = param_value
            else:
                record = StrategyParams(
                    user_id=user_id,
                    key_id=key_id,
                    symbol=symbol,
                    param_name=param_name,
                    param_value=param_value
                )
                session.add(record)
            session.commit()
        finally:
            session.close()

    @staticmethod
    def delete_for_symbol(user_id: int, symbol: str, key_id: int = None):
        """删除指定币种的所有策略参数（重置学习）"""
        session = Session()
        try:
            query = session.query(StrategyParams).filter(
                StrategyParams.user_id == user_id,
                StrategyParams.symbol == symbol
            )
            if key_id:
                query = query.filter(StrategyParams.key_id == key_id)
            query.delete()
            session.commit()
        except Exception as e:
            logger.error(f"删除策略参数失败: {e}")
            session.rollback()
        finally:
            session.close()