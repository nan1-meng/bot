# 文件路径: strategies/composite.py
"""
复合策略：将多个子策略组合成一个策略（嵌套使用）
"""
from typing import Dict, Any, List
from .base import Strategy
from .manager import StrategyManager

class CompositeStrategy(Strategy):
    def __init__(self, name: str, config: Dict[str, Any], params: Dict[str, Any] = None):
        """
        :param name: 复合策略名称
        :param config: 子策略配置（同 StrategyManager 的 config）
        :param params: 复合策略自身参数（可选）
        """
        super().__init__(name, params or {})
        self.manager = StrategyManager(config)

    def buy_score(self, data: Dict[str, Any]) -> float:
        return self.manager.compute_buy_score(data)

    def sell_score(self, data: Dict[str, Any]) -> float:
        return self.manager.compute_sell_score(data)

    def get_config(self) -> Dict[str, Any]:
        """返回子策略配置"""
        return self.manager.get_config()