# 文件路径: core/indicators.py
import math
from typing import List, Optional, Tuple

class Indicators:
    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> Optional[float]:
        if len(prices) < period + 1:
            return None
        gains, losses = [], []
        for i in range(-period, 0):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(-change)
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - 100 / (1 + rs)

    @staticmethod
    def sma(prices: List[float], period: int) -> Optional[float]:
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period

    @staticmethod
    def bollinger_bands(prices: List[float], period: int = 20, num_std: float = 2) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        if len(prices) < period:
            return None, None, None
        recent = prices[-period:]
        sma = sum(recent) / period
        variance = sum((p - sma) ** 2 for p in recent) / period
        std = math.sqrt(variance)
        upper = sma + num_std * std
        lower = sma - num_std * std
        return upper, sma, lower

    @staticmethod
    def macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        if len(prices) < slow + signal:
            return None, None, None

        def ema(data, period):
            if len(data) < period:
                return None
            alpha = 2 / (period + 1)
            ema_val = data[0]
            for p in data[1:]:
                ema_val = alpha * p + (1 - alpha) * ema_val
            return ema_val

        ema_fast = ema(prices[-fast:], fast)
        ema_slow = ema(prices[-slow:], slow)
        if ema_fast is None or ema_slow is None:
            return None, None, None
        macd_line = ema_fast - ema_slow

        macd_history = []
        for i in range(-signal, 0):
            if i >= -len(prices):
                ef = ema(prices[i-fast:i], fast)
                es = ema(prices[i-slow:i], slow)
                if ef is not None and es is not None:
                    macd_history.append(ef - es)
        if len(macd_history) < signal:
            return None, None, None
        signal_line = sum(macd_history) / signal
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram