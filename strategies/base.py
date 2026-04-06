# 文件路径: strategies/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class Strategy(ABC):
    def __init__(self, name: str, params: Dict[str, Any] = None):
        self.name = name
        self.params = params or {}
        self._cache = {}

    @abstractmethod
    def buy_score(self, data: Dict[str, Any]) -> float:
        """
        data 包含 'prices', 'volumes', 'current_price', 'dynamic_params' 等
        dynamic_params 是市场分析器推荐的动态参数，可覆盖 self.params
        """
        pass

    @abstractmethod
    def sell_score(self, data: Dict[str, Any]) -> float:
        pass

    def get_params(self) -> Dict[str, Any]:
        return self.params.copy()

    def set_params(self, params: Dict[str, Any]):
        self.params.update(params)
        self._cache.clear()

    def clear_cache(self):
        self._cache = {}