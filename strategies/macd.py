# 文件路径: strategies/macd.py
from .base import Strategy
from core.indicators import Indicators
from typing import Dict, Any

class MACDStrategy(Strategy):
    def __init__(self, params: Dict[str, Any] = None):
        default = {"fast": 12, "slow": 26, "signal": 9}
        if params:
            default.update(params)
        super().__init__("MACD", default)
        self.ind = Indicators()

    def buy_score(self, data: Dict[str, Any]) -> float:
        prices = data.get("prices")
        dynamic = data.get("dynamic_params", {}).get("MACD", {})
        fast = dynamic.get("fast", self.params["fast"])
        slow = dynamic.get("slow", self.params["slow"])
        signal = dynamic.get("signal", self.params["signal"])
        if not prices or len(prices) < slow + signal:
            return 0.0
        macd, sig, hist = self.ind.macd(prices, fast, slow, signal)
        if hist is None:
            return 0.0
        if hist > 0:
            score = min(10.0, hist * 20)
            return max(0.0, score)
        return 0.0

    def sell_score(self, data: Dict[str, Any]) -> float:
        prices = data.get("prices")
        dynamic = data.get("dynamic_params", {}).get("MACD", {})
        fast = dynamic.get("fast", self.params["fast"])
        slow = dynamic.get("slow", self.params["slow"])
        signal = dynamic.get("signal", self.params["signal"])
        if not prices or len(prices) < slow + signal:
            return 0.0
        macd, sig, hist = self.ind.macd(prices, fast, slow, signal)
        if hist is None:
            return 0.0
        if hist < 0:
            score = min(10.0, -hist * 20)
            return max(0.0, score)
        return 0.0