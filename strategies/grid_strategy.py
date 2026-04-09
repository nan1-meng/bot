# ============================================================
# 文件: strategies/grid_strategy.py
# 说明: 震荡市场网格交易策略
# ============================================================

import math
from typing import Dict, Any, Tuple, List, Optional


class GridStrategy:
    """网格交易策略，在震荡区间内低买高卖"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.grid_spacing = self.config.get("grid_spacing", 0.02)  # 网格间距2%
        self.grid_levels = self.config.get("grid_levels", 5)       # 单边网格层数
        self.base_price = None
        self.grid_prices = []
        self.filled_levels = set()  # 已成交的网格层级索引
        self.last_trade_price = None

    def initialize_grid(self, current_price: float):
        """初始化网格"""
        self.base_price = current_price
        self.grid_prices = []
        self.filled_levels = set()
        for i in range(-self.grid_levels, self.grid_levels + 1):
            if i == 0:
                continue
            price = current_price * (1 + i * self.grid_spacing)
            self.grid_prices.append((i, price))
        self.grid_prices.sort(key=lambda x: x[1])  # 按价格升序

    def get_grid_levels(self, current_price: float) -> Optional[Dict]:
        """获取当前价格对应的网格层级信息"""
        if self.base_price is None or abs(current_price - self.base_price) / self.base_price > 0.1:
            # 价格偏离基准超过10%，重新初始化
            self.initialize_grid(current_price)

        buy_levels = []
        sell_levels = []
        for idx, (level, price) in enumerate(self.grid_prices):
            if price < current_price and level not in self.filled_levels:
                buy_levels.append((level, price))
            elif price > current_price and level in self.filled_levels:
                sell_levels.append((level, price))

        return {
            "base_price": self.base_price,
            "buy_levels": buy_levels,
            "sell_levels": sell_levels,
            "current_price": current_price
        }

    def should_buy(self, data: Dict[str, Any]) -> Tuple[bool, float]:
        """判断是否买入及建议仓位比例"""
        current_price = data.get("current_price")
        usdt_balance = data.get("usdt_balance", 0)
        if current_price is None or usdt_balance <= 0:
            return False, 0.0

        if self.base_price is None:
            self.initialize_grid(current_price)

        grid_info = self.get_grid_levels(current_price)
        if not grid_info["buy_levels"]:
            return False, 0.0

        # 取最接近当前价的买单层级
        nearest_buy = min(grid_info["buy_levels"], key=lambda x: abs(x[1] - current_price))
        level, target_price = nearest_buy

        # 价格足够接近网格线（偏差小于0.2%）
        if abs(current_price - target_price) / target_price < 0.002:
            # 建议仓位比例：每层分配总资金的 1/(2*网格层数)
            position_ratio = 1.0 / (2 * self.grid_levels)
            return True, position_ratio

        return False, 0.0

    def should_sell(self, data: Dict[str, Any]) -> Tuple[bool, float]:
        """判断是否卖出及建议卖出比例"""
        current_price = data.get("current_price")
        current_qty = data.get("current_qty", 0)
        avg_price = data.get("avg_price", 0)

        if current_price is None or current_qty <= 0:
            return False, 0.0

        if self.base_price is None:
            return False, 0.0

        grid_info = self.get_grid_levels(current_price)
        if not grid_info["sell_levels"]:
            return False, 0.0

        # 取最接近当前价的卖单层级
        nearest_sell = min(grid_info["sell_levels"], key=lambda x: abs(x[1] - current_price))
        level, target_price = nearest_sell

        if abs(current_price - target_price) / target_price < 0.002:
            # 卖出该层级对应的数量
            sell_ratio = 1.0 / (2 * self.grid_levels)
            return True, sell_ratio

        return False, 0.0

    def update_after_trade(self, trade_info: Dict):
        """交易后更新已成交层级"""
        if self.base_price is None:
            return
        price = trade_info.get("price")
        side = trade_info.get("side")
        if price is None:
            return

        # 找到最近的网格层级
        min_dist = float('inf')
        matched_level = None
        for level, grid_price in self.grid_prices:
            dist = abs(price - grid_price) / grid_price
            if dist < 0.005 and dist < min_dist:
                min_dist = dist
                matched_level = level

        if matched_level is not None:
            if side == "buy":
                self.filled_levels.add(matched_level)
            elif side == "sell":
                self.filled_levels.discard(matched_level)