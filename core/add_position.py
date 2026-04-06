# 文件路径: core/add_position.py
import math
from typing import List

class AddPositionLogic:
    def __init__(self, max_times: int = 3, ratios: List[float] = None):
        self.max_times = max_times
        self.ratios = ratios or [0.5, 0.3, 0.2]

    def should_add(self, current_price: float, avg_price: float, atr_price: float,
                   market_trend: str, health_score: float, add_count: int) -> bool:
        """判断是否应该补仓，保留原始逻辑"""
        if add_count >= self.max_times:
            return False
        if market_trend == 'bear':
            return False
        if health_score < 30:
            return False
        loss_pct = (avg_price - current_price) / avg_price if avg_price != 0 else 0
        if loss_pct <= 0:
            return False
        min_loss_pct = 0.005
        if loss_pct < min_loss_pct:
            return False
        loss_atr = (avg_price - current_price) / atr_price if atr_price != 0 else 0
        if loss_atr >= 0.5 or loss_pct >= 0.03:
            return True
        return False

    def calculate_add_qty(self, initial_qty: float, add_count: int, ratios: List[float] = None) -> float:
        """计算补仓数量，保留原始逻辑"""
        if ratios is None:
            ratios = self.ratios
        if add_count >= len(ratios):
            return 0
        return initial_qty * ratios[add_count]