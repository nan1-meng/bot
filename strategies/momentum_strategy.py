# ============================================================
# 文件: strategies/momentum_strategy.py
# 说明: 趋势市场动量策略，追涨杀跌
# ============================================================

from typing import Dict, Any, Tuple, List
from core.indicators import Indicators


class MomentumStrategy:
    """动量策略：基于价格突破和均线排列追涨杀跌"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.ma_short = self.config.get("ma_short", 20)
        self.ma_long = self.config.get("ma_long", 50)
        self.lookback = self.config.get("lookback", 20)
        self.indicators = Indicators()
        self.last_signal = None

    def should_buy(self, data: Dict[str, Any]) -> Tuple[bool, float]:
        """判断是否买入及建议仓位比例"""
        prices = data.get("prices", [])
        current_price = data.get("current_price")
        if not prices or current_price is None:
            return False, 0.0

        if len(prices) < self.ma_long:
            return False, 0.0

        # 计算短期和长期均线
        sma_short = self.indicators.sma(prices, self.ma_short)
        sma_long = self.indicators.sma(prices, self.ma_long)
        if sma_short is None or sma_long is None:
            return False, 0.0

        # 计算近期高点
        recent_high = max(prices[-self.lookback:])

        # 买入条件：短期均线上穿长期均线 + 价格突破近期高点
        ma_golden_cross = sma_short > sma_long and prices[-2] < sma_short
        breakout = current_price > recent_high * 1.001  # 轻微突破

        if ma_golden_cross and breakout:
            # 根据趋势强度决定仓位
            trend_strength = (sma_short - sma_long) / sma_long
            position_ratio = min(1.0, max(0.3, 0.5 + trend_strength * 5))
            return True, position_ratio

        return False, 0.0

    def should_sell(self, data: Dict[str, Any]) -> Tuple[bool, float]:
        """判断是否卖出及建议卖出比例"""
        prices = data.get("prices", [])
        current_price = data.get("current_price")
        current_qty = data.get("current_qty", 0)
        avg_price = data.get("avg_price", 0)

        if not prices or current_price is None or current_qty <= 0:
            return False, 0.0

        if len(prices) < self.ma_long:
            return False, 0.0

        sma_short = self.indicators.sma(prices, self.ma_short)
        sma_long = self.indicators.sma(prices, self.ma_long)
        if sma_short is None or sma_long is None:
            return False, 0.0

        # 卖出条件：短期均线下穿长期均线 或 价格跌破近期低点
        ma_death_cross = sma_short < sma_long and prices[-2] > sma_short
        recent_low = min(prices[-self.lookback:])
        breakdown = current_price < recent_low * 0.999

        # 止损：亏损超过5%
        stop_loss = (current_price - avg_price) / avg_price < -0.05

        if ma_death_cross or breakdown or stop_loss:
            # 如果趋势反转强烈，全仓卖出；否则部分卖出
            if ma_death_cross:
                sell_ratio = 1.0
            elif breakdown:
                sell_ratio = 0.8
            else:
                sell_ratio = 0.5
            return True, sell_ratio

        return False, 0.0

    def update_after_trade(self, trade_info: Dict):
        """交易后更新状态（动量策略无需维护状态）"""
        pass