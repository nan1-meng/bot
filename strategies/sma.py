# 文件路径: strategies/sma.py
from .base import Strategy
from core.indicators import Indicators
from typing import Dict, Any

class SMAStrategy(Strategy):
    def __init__(self, params: Dict[str, Any] = None):
        default = {"short": 20, "long": 50}
        if params:
            default.update(params)
        super().__init__("SMA", default)
        self.ind = Indicators()

    def buy_score(self, data: Dict[str, Any]) -> float:
        prices = data.get("prices")
        dynamic = data.get("dynamic_params", {}).get("SMA", {})
        short = dynamic.get("short", self.params["short"])
        long = dynamic.get("long", self.params["long"])
        if not prices or len(prices) < long:
            return 0.0
        short_sma = self.ind.sma(prices, short)
        long_sma = self.ind.sma(prices, long)
        if short_sma is None or long_sma is None:
            return 0.0
        if short_sma > long_sma:
            diff_pct = (short_sma - long_sma) / long_sma * 100
            score = min(10.0, diff_pct)
            return max(0.0, score)
        return 0.0

    def sell_score(self, data: Dict[str, Any]) -> float:
        prices = data.get("prices")
        dynamic = data.get("dynamic_params", {}).get("SMA", {})
        short = dynamic.get("short", self.params["short"])
        long = dynamic.get("long", self.params["long"])
        if not prices or len(prices) < long:
            return 0.0
        short_sma = self.ind.sma(prices, short)
        long_sma = self.ind.sma(prices, long)
        if short_sma is None or long_sma is None:
            return 0.0
        if short_sma < long_sma:
            diff_pct = (long_sma - short_sma) / long_sma * 100
            score = min(10.0, diff_pct)
            return max(0.0, score)
        return 0.0