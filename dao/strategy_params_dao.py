# 文件路径: dao/strategy_params_dao.py
import json
from models.strategy_params import StrategyParams
from utils.db import Session

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
            # 兼容旧数据
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
                # 特殊处理列表类型参数
                if param_name == "add_position_ratios":
                    try:
                        return json.loads(record.param_value)
                    except:
                        # 兼容旧数据，尝试解析逗号分隔的字符串
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
            # 将列表转换为 JSON 字符串存储
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