# 文件路径: core/signal_engine.py
import math
from typing import List, Optional, Tuple
from core.indicators import Indicators

class SignalEngine:
    def __init__(self):
        self.ind = Indicators()

    def calculate_atr(self, highs: List[float], lows: List[float], period: int = 14) -> float:
        """计算ATR（平均真实波幅）"""
        if len(highs) < period or len(lows) < period:
            return 0.0
        tr_list = []
        for i in range(-period, 0):
            tr = highs[i] - lows[i]
            tr_list.append(tr)
        return sum(tr_list) / period

    def realtime_range_score(self, highs: List[float], lows: List[float], current_price: float,
                              period: int = 20, volumes: List[float] = None) -> float:
        """
        基于实时价格与近期高低点的位置计算评分（0-100）
        """
        if len(highs) < period or len(lows) < period:
            return 0.0
        recent_high = max(highs[-period:])
        recent_low = min(lows[-period:])
        if recent_high == recent_low:
            return 0.0

        # 价格在区间中的位置得分（0~100）
        position_score = (current_price - recent_low) / (recent_high - recent_low) * 100

        # 突破加分：价格超过近期高点，额外加分
        if current_price > recent_high:
            breakout_extra = min(50, (current_price - recent_high) / recent_high * 500)
            position_score = min(100, position_score + breakout_extra)
        # 回调加分：价格低于近期低点，额外加分（抄底）
        elif current_price < recent_low:
            pullback_extra = min(50, (recent_low - current_price) / recent_low * 500)
            # 价格低于低点时，我们更想买入，所以加分（反向）
            position_score = min(100, position_score + pullback_extra)
        # 正常区间内，不做额外调整
        else:
            pass

        # 成交量因子（可选）
        vol_factor = 1.0
        if volumes and len(volumes) >= period:
            avg_vol = sum(volumes[-period:]) / period
            if avg_vol > 0:
                vol_ratio = volumes[-1] / avg_vol
                if vol_ratio > 1.2:
                    vol_factor = 1.2
                elif vol_ratio < 0.8:
                    vol_factor = 0.8

        final_score = position_score * vol_factor
        return min(100, max(0, final_score))

    def breakout_score(self, prices: List[float], highs: List[float], volumes: List[float], current_price: float = None) -> float:
        """突破信号评分（已弃用，保留兼容性）"""
        if len(prices) < 20:
            return 0
        recent_high = max(highs[-20:])
        if current_price is None:
            current_price = prices[-1]
        if current_price <= recent_high:
            return 0
        breakout_pct = (current_price - recent_high) / recent_high * 100
        if len(volumes) >= 20:
            avg_vol = sum(volumes[-20:]) / 20
            vol_ratio = volumes[-1] / avg_vol if avg_vol > 0 else 1.0
        else:
            vol_ratio = 1.0
        if vol_ratio < 1.2:
            return 0
        score = min(100, breakout_pct * 10 + (vol_ratio - 1) * 20)
        return score

    def pullback_score(self, prices: List[float], highs: List[float], lows: List[float],
                       volumes: List[float] = None, current_price: float = None) -> float:
        """回调买入信号评分（已弃用，保留兼容性）"""
        if len(prices) < 20:
            return 0
        sma20 = self.ind.sma(prices, 20)
        if sma20 is None:
            return 0
        price = current_price if current_price is not None else prices[-1]
        deviation = abs(price - sma20) / sma20
        if deviation > 0.015:
            return 0
        base_score = 100 - deviation * 100
        vol_coef = 1.0
        if volumes and len(volumes) >= 20:
            avg_vol = sum(volumes[-20:]) / 20
            if avg_vol > 0:
                vol_ratio = volumes[-1] / avg_vol
                vol_coef = 0.5 + min(1.0, max(0.0, (vol_ratio - 0.5) / 1.5)) * 1.0
                vol_coef = min(1.5, max(0.5, vol_coef))
        rsi_val = self.ind.rsi(prices, 14)
        rsi_coef = 1.0
        if rsi_val is not None:
            if rsi_val < 50:
                rsi_coef = 1 + (50 - rsi_val) / 50 * 0.5
                rsi_coef = min(1.5, rsi_coef)
            elif rsi_val > 70:
                rsi_coef = 1 - (rsi_val - 70) / 30 * 0.5
                rsi_coef = max(0.5, rsi_coef)
        if len(highs) >= 10:
            recent_highs = highs[-10:]
            if recent_highs[-1] <= recent_highs[0]:
                trend_factor = 0.8
            else:
                trend_factor = 1.0
        else:
            trend_factor = 1.0
        score = base_score * vol_coef * rsi_coef * trend_factor
        return min(100, max(0, score))

    def rsi_score(self, prices: List[float], period: int = 14, current_price: float = None) -> float:
        """RSI超卖反弹评分（保留）"""
        rsi = self.ind.rsi(prices, period)
        if rsi is None:
            return 0
        if rsi < 30:
            return (30 - rsi) / 30 * 100
        return 0

    def volume_score(self, volumes: List[float]) -> float:
        """成交量异常放大评分（保留）"""
        if len(volumes) < 20:
            return 0
        avg_vol = sum(volumes[-20:]) / 20
        if avg_vol == 0:
            return 0
        vol_ratio = volumes[-1] / avg_vol
        if vol_ratio > 1.2:
            return min(100, (vol_ratio - 1) * 100)
        return 0

    def combine_scores(self, scores: List[float], weights: List[float] = None) -> float:
        """加权合并多个评分"""
        if not scores:
            return 0
        if weights is None:
            weights = [1.0] * len(scores)
        total_weight = sum(weights)
        if total_weight == 0:
            return 0
        weighted = sum(s * w for s, w in zip(scores, weights))
        return weighted / total_weight