# 文件路径: core/risk_manager.py
from typing import Dict, Optional, Any
from dao.coin_health_dao import CoinHealthDAO
from dao.strategy_params_dao import StrategyParamsDAO
from models.strategy_params import StrategyParams
from models.coin_health import CoinHealth
from utils.db import Session
import json

class RiskManager:
    def __init__(self, key_id: int, user_id: int, online_learner=None):
        self.key_id = key_id
        self.user_id = user_id
        self.online_learner = online_learner  # 可选，用于实时学习
        self.health_cache: Dict[str, float] = {}
        self._load_all_health()

        # 动态参数缓存（全局 + 币种级）
        self.global_params: Dict[str, Any] = {}
        self.symbol_params: Dict[str, Dict[str, Any]] = {}
        self._load_all_params()

    def _load_all_health(self):
        session = Session()
        try:
            records = CoinHealthDAO.get_all_by_key(self.key_id, session)
            for rec in records:
                self.health_cache[rec.symbol] = rec.health_score
        finally:
            session.close()

    def _load_all_params(self):
        session = Session()
        try:
            # 加载全局参数（优先 user_id 级别，兼容 key_id）
            global_records = session.query(StrategyParams).filter(
                StrategyParams.user_id == self.user_id,
                StrategyParams.symbol.is_(None)
            ).all()
            if not global_records:
                # 兼容旧数据：尝试从 key_id 加载
                global_records = session.query(StrategyParams).filter(
                    StrategyParams.key_id == self.key_id,
                    StrategyParams.symbol.is_(None)
                ).all()
            for p in global_records:
                self.global_params[p.param_name] = self._parse_param_value(p.param_value)

            # 加载币种参数（优先 user_id，兼容 key_id）
            symbol_records = session.query(StrategyParams).filter(
                StrategyParams.user_id == self.user_id,
                StrategyParams.symbol.isnot(None)
            ).all()
            if not symbol_records:
                symbol_records = session.query(StrategyParams).filter(
                    StrategyParams.key_id == self.key_id,
                    StrategyParams.symbol.isnot(None)
                ).all()
            for p in symbol_records:
                if p.symbol not in self.symbol_params:
                    self.symbol_params[p.symbol] = {}
                self.symbol_params[p.symbol][p.param_name] = self._parse_param_value(p.param_value)
        finally:
            session.close()

    def _parse_param_value(self, value: str) -> Any:
        """尝试将字符串解析为 JSON，否则返回原值（转为 float 或原字符串）"""
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            return float(value)
        except ValueError:
            return value

    def _serialize_param_value(self, value: Any) -> str:
        """将参数值序列化为字符串（JSON 或直接转 str）"""
        if isinstance(value, (list, dict)):
            return json.dumps(value)
        elif isinstance(value, (int, float)):
            return str(value)
        else:
            return str(value)

    # ---------- 健康度相关 ----------
    def get_health_score(self, symbol: str) -> float:
        return self.health_cache.get(symbol, 60.0)

    def update_health(self, symbol: str, pnl_usdt: float, is_win: bool):
        health = self.get_health_score(symbol)
        if is_win:
            health = min(100, health + 3)
            if pnl_usdt > 0:
                health = min(100, health + 2)
        else:
            health = max(10, health - 4)
            if pnl_usdt < 0:
                health = max(10, health - 3)
        self.health_cache[symbol] = health
        session = Session()
        try:
            CoinHealthDAO.upsert(self.key_id, symbol, health, session)
            session.commit()
        finally:
            session.close()

    # ---------- 动态参数获取 ----------
    def get_param(self, param_name: str, symbol: str = None, default: Any = None) -> Any:
        if symbol and symbol in self.symbol_params and param_name in self.symbol_params[symbol]:
            return self.symbol_params[symbol][param_name]
        if param_name in self.global_params:
            return self.global_params[param_name]
        return default

    def set_param(self, param_name: str, param_value: Any, symbol: str = None):
        # 序列化参数值
        serialized = self._serialize_param_value(param_value)
        StrategyParamsDAO.set_param(self.user_id, param_name, serialized, symbol, key_id=self.key_id)
        # 更新缓存
        parsed = self._parse_param_value(serialized)
        if symbol is None:
            self.global_params[param_name] = parsed
        else:
            if symbol not in self.symbol_params:
                self.symbol_params[symbol] = {}
            self.symbol_params[symbol][param_name] = parsed

    # ---------- 动态阈值/仓位计算（使用参数） ----------
    def get_position_ratio(self, symbol: str) -> float:
        base_ratio = self.get_param("position_ratio_base", symbol, 0.5)
        if isinstance(base_ratio, (list, dict)):
            base_ratio = 0.5
        health = self.get_health_score(symbol)
        ratio = base_ratio * (health / 100.0)
        min_ratio = self.get_param("min_position_ratio", symbol, 0.1)
        if isinstance(min_ratio, (list, dict)):
            min_ratio = 0.1
        max_ratio = self.get_param("max_position_ratio", symbol, 1.0)
        if isinstance(max_ratio, (list, dict)):
            max_ratio = 1.0
        return max(min_ratio, min(max_ratio, ratio))

    def get_buy_threshold_adjustment(self, symbol: str) -> float:
        health = self.get_health_score(symbol)
        base_adjust = (60 - health) * 0.5
        max_adj = self.get_param("max_threshold_adjust", symbol, 20)
        if isinstance(max_adj, (list, dict)):
            max_adj = 20
        min_adj = self.get_param("min_threshold_adjust", symbol, -10)
        if isinstance(min_adj, (list, dict)):
            min_adj = -10
        return max(min_adj, min(max_adj, base_adjust))

    def get_dynamic_stop_loss_atr_mult(self, symbol: str) -> float:
        health = self.get_health_score(symbol)
        if health < 30:
            base = 2.0
        elif health < 60:
            base = 1.8
        else:
            base = 1.5
        val = self.get_param("stop_loss_atr_mult", symbol, base)
        if isinstance(val, (list, dict)):
            val = base
        return val

    def get_dynamic_take_profit_mult(self, symbol: str) -> list:
        health = self.get_health_score(symbol)
        if health > 70:
            base = [1.5, 2.5, 4.0]
        elif health < 30:
            base = [1.0, 1.5, 2.5]
        else:
            base = [1.0, 2.0, 3.0]
        val = self.get_param("take_profit_atr_mult", symbol, base)
        if isinstance(val, list):
            return val
        return base

    def can_add_position(self, symbol: str) -> bool:
        health = self.get_health_score(symbol)
        min_health = self.get_param("min_health_for_add", symbol, 30)
        if isinstance(min_health, (list, dict)):
            min_health = 30
        return health >= min_health

    def can_buy(self, symbol: str, amount: float) -> bool:
        return True

    def can_sell(self, symbol: str, qty: float) -> bool:
        return True

    def get_last_reason(self) -> str:
        return ""