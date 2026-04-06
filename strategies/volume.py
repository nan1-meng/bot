# 文件路径: strategies/volume.py
from .base import Strategy
from typing import Dict, Any

class VolumeStrategy(Strategy):
    def __init__(self, params: Dict[str, Any] = None):
        default = {"period": 20, "ratio": 1.2}
        if params:
            default.update(params)
        super().__init__("Volume", default)

    def buy_score(self, data: Dict[str, Any]) -> float:
        volumes = data.get("volumes")
        dynamic = data.get("dynamic_params", {}).get("Volume", {})
        period = dynamic.get("period", self.params["period"])
        ratio = dynamic.get("ratio", self.params["ratio"])
        if not volumes or len(volumes) < period:
            return 0.0
        avg_vol = sum(volumes[-period:]) / period
        current_vol = volumes[-1]
        if current_vol > avg_vol * ratio:
            score = (current_vol / avg_vol - ratio) / (2.0 - ratio) * 10.0
            return min(10.0, max(0.0, score))
        return 0.0

    def sell_score(self, data: Dict[str, Any]) -> float:
        return 0.0