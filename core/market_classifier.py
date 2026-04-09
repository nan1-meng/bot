# ============================================================
# 文件: core/market_classifier.py
# 说明: 实时判断市场状态（趋势/震荡/高波动），用于策略切换
# ============================================================

import numpy as np
from typing import List, Tuple
from core.indicators import Indicators


class MarketClassifier:
    """市场状态分类器，基于ADX、布林带宽度、价格效率比"""

    def __init__(self, adx_period: int = 14, bb_period: int = 20, bb_std: float = 2.0):
        self.adx_period = adx_period
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.indicators = Indicators()

    def classify(self, highs: List[float], lows: List[float], closes: List[float]) -> dict:
        """
        返回市场状态字典，包含：
        - state: 'trending' (趋势), 'ranging' (震荡), 'high_volatility' (高波动)
        - adx: ADX值
        - bb_width_ratio: 布林带宽度与价格比
        - efficiency_ratio: 价格效率比
        """
        if len(closes) < max(self.adx_period, self.bb_period) + 1:
            return {"state": "unknown", "adx": 0, "bb_width_ratio": 0, "efficiency_ratio": 0}

        # 1. 计算ADX判断趋势强度
        adx = self._calculate_adx(highs, lows, closes, self.adx_period)

        # 2. 计算布林带宽度与价格比，判断波动率
        bb_upper, bb_mid, bb_lower = self.indicators.bollinger_bands(
            closes, self.bb_period, self.bb_std
        )
        if bb_mid is None or bb_mid == 0:
            bb_width_ratio = 0
        else:
            bb_width = bb_upper - bb_lower
            bb_width_ratio = bb_width / bb_mid

        # 3. 价格效率比（Efficiency Ratio），判断趋势vs震荡
        er = self._efficiency_ratio(closes, period=10)

        # 综合判定
        if adx > 25:
            state = "trending"
        elif bb_width_ratio > 0.05:
            state = "high_volatility"
        elif er < 0.3:
            state = "ranging"
        else:
            state = "ranging"  # 默认震荡

        return {
            "state": state,
            "adx": adx,
            "bb_width_ratio": bb_width_ratio,
            "efficiency_ratio": er
        }

    def _calculate_adx(self, highs: List[float], lows: List[float], closes: List[float], period: int) -> float:
        """计算ADX"""
        if len(closes) < period + 1:
            return 0.0

        tr = []
        plus_dm = []
        minus_dm = []
        for i in range(1, len(closes)):
            high = highs[i]
            low = lows[i]
            prev_high = highs[i-1]
            prev_low = lows[i-1]
            prev_close = closes[i-1]

            # True Range
            tr.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))

            # Directional Movement
            up_move = high - prev_high
            down_move = prev_low - low
            if up_move > down_move and up_move > 0:
                plus_dm.append(up_move)
            else:
                plus_dm.append(0)
            if down_move > up_move and down_move > 0:
                minus_dm.append(down_move)
            else:
                minus_dm.append(0)

        if len(tr) < period:
            return 0.0

        # 平滑
        atr = self._wilders_smoothing(tr[-period:], period)
        plus_di = self._wilders_smoothing(plus_dm[-period:], period) / atr * 100 if atr != 0 else 0
        minus_di = self._wilders_smoothing(minus_dm[-period:], period) / atr * 100 if atr != 0 else 0
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) != 0 else 0
        adx = dx  # 简化，通常需要再次平滑，这里直接返回DX作为近似
        return adx

    def _wilders_smoothing(self, values: List[float], period: int) -> float:
        """Wilder平滑"""
        if not values:
            return 0.0
        smoothed = values[0]
        for v in values[1:]:
            smoothed = (smoothed * (period - 1) + v) / period
        return smoothed

    def _efficiency_ratio(self, closes: List[float], period: int = 10) -> float:
        """价格效率比 = 净变化 / 路径总长度"""
        if len(closes) < period:
            return 0.0
        net_change = abs(closes[-1] - closes[-period])
        path_length = sum(abs(closes[i] - closes[i-1]) for i in range(-period+1, 0))
        if path_length == 0:
            return 0.0
        return net_change / path_length