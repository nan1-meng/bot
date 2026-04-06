# 文件路径: strategies/rsi.py
from .base import Strategy
from core.indicators import Indicators
from typing import Dict, Any

class RSIStrategy(Strategy):
    def __init__(self, params: Dict[str, Any] = None):
        default = {"period": 14, "oversold": 30, "overbought": 70}
        if params:
            default.update(params)
        super().__init__("RSI", default)
        self.ind = Indicators()

    def buy_score(self, data: Dict[str, Any]) -> float:
        prices = data.get("prices")
        dynamic = data.get("dynamic_params", {}).get("RSI", {})
        period = dynamic.get("period", self.params["period"])
        oversold = dynamic.get("oversold", self.params["oversold"])
        if not prices or len(prices) < period:
            return 0.0
        rsi = self.ind.rsi(prices, period)
        if rsi is None:
            return 0.0
        if rsi < oversold:
            score = (oversold - rsi) / oversold * 10.0
            return min(10.0, max(0.0, score))
        return 0.0

    def sell_score(self, data: Dict[str, Any]) -> float:
        prices = data.get("prices")
        dynamic = data.get("dynamic_params", {}).get("RSI", {})
        period = dynamic.get("period", self.params["period"])
        overbought = dynamic.get("overbought", self.params["overbought"])
        if not prices or len(prices) < period:
            return 0.0
        rsi = self.ind.rsi(prices, period)
        if rsi is None:
            return 0.0
        if rsi > overbought:
            score = (rsi - overbought) / (100 - overbought) * 10.0
            return min(10.0, max(0.0, score))
        return 0.0