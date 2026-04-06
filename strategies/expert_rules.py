# 文件路径: strategies/expert_rules.py
import math
from typing import List, Dict, Any

class ExpertRules:
    """
    封装 BIT浪浪风格的技术分析规则
    """
    def __init__(self):
        pass

    def fibonacci_level(self, high: float, low: float, current: float) -> float:
        """计算当前价格在斐波那契回调中的位置（0~1）"""
        if high == low:
            return 0.5
        ratio = (current - low) / (high - low)
        # 斐波那契关键位: 0.236, 0.382, 0.5, 0.618, 0.786
        levels = [0.236, 0.382, 0.5, 0.618, 0.786]
        # 找出最近的级别，返回得分
        if ratio >= 0.786:
            return 1.0
        elif ratio >= 0.618:
            return 0.8
        elif ratio >= 0.5:
            return 0.6
        elif ratio >= 0.382:
            return 0.4
        elif ratio >= 0.236:
            return 0.2
        else:
            return 0.0

    def wave_pattern_score(self, prices: List[float]) -> float:
        """
        识别简单的波浪形态（上升5浪、下降5浪）
        返回0~1的分数
        """
        if len(prices) < 20:
            return 0.0
        # 取最近20个收盘价
        recent = prices[-20:]
        # 简单判断上升趋势
        uptrend = recent[-1] > recent[0]
        # 寻找极值点
        peaks = []
        troughs = []
        for i in range(1, len(recent)-1):
            if recent[i] > recent[i-1] and recent[i] > recent[i+1]:
                peaks.append((i, recent[i]))
            if recent[i] < recent[i-1] and recent[i] < recent[i+1]:
                troughs.append((i, recent[i]))
        if uptrend:
            # 上升浪应至少有3个峰谷
            if len(peaks) >= 2 and len(troughs) >= 2:
                return 0.7
        else:
            if len(troughs) >= 2 and len(peaks) >= 2:
                return 0.7
        return 0.0

    def support_resistance(self, highs: List[float], lows: List[float], current: float) -> float:
        """
        判断当前价格是否在关键支撑/阻力位附近
        """
        if len(highs) < 20 or len(lows) < 20:
            return 0.0
        recent_high = max(highs[-20:])
        recent_low = min(lows[-20:])
        # 接近阻力位
        if current > recent_high * 0.98:
            return -0.5   # 阻力位附近，卖出信号
        # 接近支撑位
        if current < recent_low * 1.02:
            return 0.8    # 支撑位附近，买入信号
        return 0.0

    def evaluate(self, prices: List[float], highs: List[float], lows: List[float],
                 current_price: float, market_features: Dict[str, float]) -> float:
        """
        综合评估，返回 -1（卖出）到 1（买入）之间的分数
        """
        fib_score = self.fibonacci_level(max(highs[-50:]), min(lows[-50:]), current_price)
        wave_score = self.wave_pattern_score(prices)
        sr_score = self.support_resistance(highs, lows, current_price)

        # 结合庄家特征
        big_net = market_features.get('big_trade_net_flow', 0)
        volume_anomaly = market_features.get('volume_anomaly', 1.0)
        obv_trend = market_features.get('obv_trend', 0)

        # 大单净流入为正加分，为负减分
        big_trade_score = min(0.3, max(-0.3, big_net / 10000))  # 每1万USDT ±0.1分
        # 成交量异常放大且价格在低位，加分
        vol_score = 0.0
        if volume_anomaly > 1.5 and current_price < max(highs[-20:]) * 0.95:
            vol_score = 0.2
        # OBV趋势向上加分
        obv_score = min(0.2, max(-0.2, obv_trend / 10000))

        total = fib_score * 0.3 + wave_score * 0.2 + sr_score * 0.2 + big_trade_score + vol_score + obv_score
        return max(-1.0, min(1.0, total))