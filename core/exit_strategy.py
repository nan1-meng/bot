# 文件路径: core/exit_strategy.py
import math
from typing import Tuple, List

class ExitStrategy:
    def __init__(self, atr_multipliers: List[float] = None, sell_ratios: List[float] = None):
        self.atr_multipliers = atr_multipliers or [1.0, 2.0, 3.0]
        self.sell_ratios = sell_ratios or [0.2, 0.3, 0.5]

    def should_sell_full(self, profit_pct: float, rsi: float, volume_ratio: float,
                         market_trend: str, hold_hours: float) -> bool:
        conditions = 0
        if profit_pct > 3 * self.atr_multipliers[-1]:
            conditions += 1
        if rsi > 85:
            conditions += 1
        if volume_ratio > 2.0:
            conditions += 1
        if market_trend == 'bear':
            conditions += 1
        if hold_hours > 72:
            conditions += 1
        return conditions >= 2

    def calculate_sell_orders(self, current_qty: float, current_price: float,
                              avg_price: float, atr_price: float,
                              rsi: float, volume_ratio: float,
                              market_trend: str, hold_hours: float) -> List[Tuple[float, float]]:
        profit_pct = (current_price - avg_price) / avg_price * 100 if avg_price != 0 else 0
        if profit_pct <= 0:
            return []

        # 检查全仓条件
        if self.should_sell_full(profit_pct, rsi, volume_ratio, market_trend, hold_hours):
            return [(current_qty, current_price)]

        # 分仓卖出，但限制最大订单数（例如最多3个）
        sell_orders = []
        remaining_qty = current_qty
        max_orders = 3  # 最多产生3个订单
        for i, (mult, ratio) in enumerate(zip(self.atr_multipliers, self.sell_ratios)):
            if i >= max_orders:
                break
            target_profit_pct = mult * (atr_price / avg_price) * 100 if avg_price != 0 else 0
            if profit_pct >= target_profit_pct:
                sell_qty = remaining_qty * ratio
                if sell_qty > 0:
                    sell_orders.append((sell_qty, current_price))
                    remaining_qty -= sell_qty
            else:
                break
        return sell_orders