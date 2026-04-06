# 文件路径: strategies/manager.py
from typing import Dict, Any, List, Callable, Optional
from .base import Strategy
from .rsi import RSIStrategy
from .bollinger import BollingerStrategy
from .macd import MACDStrategy
from .sma import SMAStrategy
from .volume import VolumeStrategy
from .loader import load_custom_strategy

class StrategyManager:
    def __init__(self, config: Dict[str, Any], debug_callback: Optional[Callable[[str], None]] = None):
        self.config = config
        self.strategies: List[Strategy] = []
        self.weights: List[float] = []
        self.combine_mode = config.get("combine_mode", "weighted")
        self.debug_callback = debug_callback
        self._load_strategies()

    def _load_strategies(self):
        builtin_map = {
            "RSI": RSIStrategy,
            "Bollinger": BollingerStrategy,
            "MACD": MACDStrategy,
            "SMA": SMAStrategy,
            "Volume": VolumeStrategy,
        }
        for item in self.config.get("strategies", []):
            if not item.get("enabled", True):
                continue
            name = item["name"]
            weight = item.get("weight", 1.0)
            params = item.get("params", {})
            cls = builtin_map.get(name)
            if cls:
                self.strategies.append(cls(params))
                self.weights.append(weight)

    def compute_buy_score(self, data: Dict[str, Any]) -> float:
        if not self.strategies:
            return 0.0
        scores = []
        for s in self.strategies:
            try:
                score = s.buy_score(data)
                scores.append(score)
                if self.debug_callback:
                    self.debug_callback(f"{s.name}买入分={score:.2f}")
            except Exception as e:
                if self.debug_callback:
                    self.debug_callback(f"{s.name}评分异常: {e}")
                scores.append(0.0)
        combined = self._combine(scores)
        if self.debug_callback:
            self.debug_callback(f"合并买入分={combined:.2f} (模式={self.combine_mode})")
        return combined

    def compute_sell_score(self, data: Dict[str, Any]) -> float:
        if not self.strategies:
            return 0.0
        scores = []
        for s in self.strategies:
            try:
                score = s.sell_score(data)
                scores.append(score)
                if self.debug_callback:
                    self.debug_callback(f"{s.name}卖出分={score:.2f}")
            except Exception as e:
                if self.debug_callback:
                    self.debug_callback(f"{s.name}评分异常: {e}")
                scores.append(0.0)
        combined = self._combine(scores)
        if self.debug_callback:
            self.debug_callback(f"合并卖出分={combined:.2f}")
        return combined

    def _combine(self, scores: List[float]) -> float:
        if not scores:
            return 0.0
        if self.combine_mode == "weighted":
            total_weight = sum(self.weights)
            if total_weight == 0:
                return 0.0
            weighted = sum(s * w for s, w in zip(scores, self.weights))
            return weighted / total_weight
        elif self.combine_mode == "max":
            return max(scores)
        elif self.combine_mode == "min":
            return min(scores)
        else:
            return sum(scores) / len(scores)

    def get_active_strategies(self) -> List[str]:
        return [s.name for s in self.strategies]

    def get_config(self) -> Dict[str, Any]:
        config = {"strategies": [], "combine_mode": self.combine_mode}
        for s, w in zip(self.strategies, self.weights):
            config["strategies"].append({
                "name": s.name,
                "enabled": True,
                "weight": w,
                "params": s.get_params()
            })
        return config

    def update_weights(self, new_weights: Dict[str, float]):
        for i, s in enumerate(self.strategies):
            if s.name in new_weights:
                self.weights[i] = new_weights[s.name]

    def update_params(self, dynamic_params: Dict[str, Dict[str, Any]]):
        for s in self.strategies:
            if s.name in dynamic_params:
                s.set_params(dynamic_params[s.name])