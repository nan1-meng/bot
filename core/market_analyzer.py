# 文件路径: core/market_analyzer.py
import math
from typing import List, Dict, Any, Tuple
from collections import deque

class MarketAnalyzer:
    def __init__(self, lookback: int = 50):
        self.lookback = lookback
        self.prices = deque(maxlen=lookback)
        self.highs = deque(maxlen=lookback)
        self.lows = deque(maxlen=lookback)
        self.volumes = deque(maxlen=lookback)

    def update(self, price: float, high: float, low: float, volume: float):
        self.prices.append(price)
        self.highs.append(high)
        self.lows.append(low)
        self.volumes.append(volume)

    def get_state(self) -> Dict[str, Any]:
        """返回市场状态字典（已有）"""
        if len(self.prices) < 20:
            return {"trend": "neutral", "volatility": "low", "volume": "normal", "score": 0}

        sma20 = self._sma(list(self.prices), 20)
        sma50 = self._sma(list(self.prices), 50)
        trend_strength = 0
        if sma20 is not None and sma50 is not None:
            trend_strength = (sma20 - sma50) / sma50 * 100

        adx = self._calculate_adx()
        atr = self._calculate_atr()
        current_price = self.prices[-1]
        volatility_ratio = atr / current_price if current_price != 0 else 0

        avg_volume = self._sma(list(self.volumes), 20) if len(self.volumes) >= 20 else 0
        current_volume = self.volumes[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        if abs(trend_strength) > 2 and adx > 25:
            trend = "bull" if trend_strength > 0 else "bear"
        else:
            trend = "neutral"

        if volatility_ratio > 0.03:
            volatility = "high"
        elif volatility_ratio < 0.01:
            volatility = "low"
        else:
            volatility = "normal"

        if volume_ratio > 1.5:
            volume = "high"
        elif volume_ratio < 0.7:
            volume = "low"
        else:
            volume = "normal"

        return {
            "trend": trend,
            "trend_strength": trend_strength,
            "adx": adx,
            "volatility": volatility,
            "volatility_ratio": volatility_ratio,
            "volume": volume,
            "volume_ratio": volume_ratio,
            "score": self._calculate_score(trend, volatility, volume)
        }

    def get_state_string(self) -> str:
        """返回简化的市场状态字符串（用于记录）"""
        state = self.get_state()
        if state['trend'] != 'neutral':
            return 'trend'
        elif state['volatility'] == 'high':
            return 'high_volatility'
        else:
            return 'range'

    def _sma(self, data: List[float], period: int) -> float:
        if len(data) < period:
            return None
        return sum(data[-period:]) / period

    def _calculate_atr(self, period: int = 14) -> float:
        if len(self.highs) < period + 1:
            return 0.0
        tr_list = []
        for i in range(-period, 0):
            high = self.highs[i]
            low = self.lows[i]
            prev_close = self.prices[i-1] if i-1 >= -len(self.prices) else self.prices[0]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)
        return sum(tr_list) / period

    def _calculate_adx(self, period: int = 14) -> float:
        if len(self.prices) < period + 1:
            return 0
        plus_dm = []
        minus_dm = []
        tr = []
        for i in range(-period, 0):
            high = self.highs[i]
            low = self.lows[i]
            prev_high = self.highs[i-1]
            prev_low = self.lows[i-1]
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
            tr_val = max(high - low, abs(high - self.prices[i-1]), abs(low - self.prices[i-1]))
            tr.append(tr_val)

        if sum(tr) == 0:
            return 0
        plus_di = sum(plus_dm) / sum(tr) * 100
        minus_di = sum(minus_dm) / sum(tr) * 100
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if plus_di + minus_di != 0 else 0
        return dx

    def _calculate_score(self, trend: str, volatility: str, volume: str) -> float:
        score = 0
        if trend == "bull":
            score += 0.5
        elif trend == "bear":
            score -= 0.5
        if volatility == "high":
            score += 0.3
        elif volatility == "low":
            score -= 0.2
        if volume == "high":
            score += 0.2
        return max(-1.0, min(1.0, score))