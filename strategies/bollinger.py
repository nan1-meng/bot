# 文件路径: strategies/bollinger.py
from .base import Strategy
from core.indicators import Indicators
from typing import Dict, Any

class BollingerStrategy(Strategy):
    def __init__(self, params: Dict[str, Any] = None):
        default = {"period": 20, "num_std": 2}
        if params:
            default.update(params)
        super().__init__("Bollinger", default)
        self.ind = Indicators()

    def buy_score(self, data: Dict[str, Any]) -> float:
        prices = data.get("prices")
        current_price = data.get("current_price")
        dynamic = data.get("dynamic_params", {}).get("Bollinger", {})
        period = dynamic.get("period", self.params["period"])
        num_std = dynamic.get("num_std", self.params["num_std"])
        if not prices or len(prices) < period or not current_price:
            return 0.0
        upper, mid, lower = self.ind.bollinger_bands(prices, period, num_std)
        if lower is None:
            return 0.0
        if current_price < lower:
            band_width = (upper - lower) if upper and lower else 1.0
            deviation = (lower - current_price) / band_width if band_width != 0 else 0.0
            score = min(10.0, max(0.0, deviation * 10.0))
            return score
        return 0.0

    def sell_score(self, data: Dict[str, Any]) -> float:
        prices = data.get("prices")
        current_price = data.get("current_price")
        dynamic = data.get("dynamic_params", {}).get("Bollinger", {})
        period = dynamic.get("period", self.params["period"])
        num_std = dynamic.get("num_std", self.params["num_std"])
        if not prices or len(prices) < period or not current_price:
            return 0.0
        upper, mid, lower = self.ind.bollinger_bands(prices, period, num_std)
        if upper is None:
            return 0.0
        if current_price > upper:
            band_width = (upper - lower) if upper and lower else 1.0
            deviation = (current_price - upper) / band_width if band_width != 0 else 0.0
            score = min(10.0, max(0.0, deviation * 10.0))
            return score
        return 0.0