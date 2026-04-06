# 文件路径: core/market_features.py
import time
from collections import deque
from typing import Dict, List, Optional
import threading

class MarketFeatures:
    def __init__(self, symbol: str, lookback_seconds: int = 60):
        self.symbol = symbol
        self.lookback_seconds = lookback_seconds
        self.trades = deque(maxlen=10000)  # 存储更多
        self.obv = 0.0
        self.obv_history = deque(maxlen=100)  # 存储最近100个OBV值，用于趋势
        self.prev_close = None
        self.big_trade_threshold = 10000
        self._lock = threading.RLock()

    def update_trade(self, trade: Dict):
        with self._lock:
            # 标准化字段
            if 'price' in trade:
                price = float(trade['price'])
                qty = float(trade['size'])
                is_buy = trade['side'] == 'Buy'
            elif 'p' in trade:
                price = float(trade['p'])
                qty = float(trade['q'])
                is_buy = not trade['m']   # Binance: m=True表示卖方主动
            else:
                return
            timestamp = trade.get('timestamp', trade.get('T', time.time()*1000)) / 1000.0

            # 更新 OBV
            if self.prev_close is not None:
                if price > self.prev_close:
                    self.obv += qty
                elif price < self.prev_close:
                    self.obv -= qty
            self.prev_close = price
            self.obv_history.append(self.obv)

            # 记录成交
            self.trades.append({
                'timestamp': timestamp,
                'price': price,
                'qty': qty,
                'is_buy': is_buy,
                'value': price * qty
            })

    def get_big_trade_net_flow(self, seconds: int = None) -> float:
        with self._lock:
            if seconds is None:
                seconds = self.lookback_seconds
            cutoff = time.time() - seconds
            net = 0.0
            for t in self.trades:
                if t['timestamp'] >= cutoff and t['value'] >= self.big_trade_threshold:
                    net += t['value'] if t['is_buy'] else -t['value']
            return net

    def get_volume_anomaly(self, seconds: int = 30) -> float:
        with self._lock:
            cutoff = time.time() - seconds
            recent_vol = sum(t['qty'] for t in self.trades if t['timestamp'] >= cutoff)
            # 计算历史平均每秒成交量（基于所有数据）
            if not self.trades:
                return 1.0
            total_vol = sum(t['qty'] for t in self.trades)
            time_span = self.trades[-1]['timestamp'] - self.trades[0]['timestamp']
            if time_span <= 0:
                return 1.0
            avg_vol_per_sec = total_vol / time_span
            expected_vol = avg_vol_per_sec * seconds
            if expected_vol == 0:
                return 1.0
            return recent_vol / expected_vol

    def get_obv_trend(self) -> float:
        with self._lock:
            if len(self.obv_history) < 2:
                return 0.0
            # 计算最近10个OBV值的斜率（简单线性回归）
            n = min(10, len(self.obv_history))
            recent = list(self.obv_history)[-n:]
            x = list(range(n))
            y = recent
            mean_x = sum(x) / n
            mean_y = sum(y) / n
            numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
            denominator = sum((x[i] - mean_x) ** 2 for i in range(n))
            if denominator == 0:
                return 0.0
            slope = numerator / denominator
            return slope

    def get_features(self) -> Dict[str, float]:
        return {
            'big_trade_net_flow': self.get_big_trade_net_flow(),
            'volume_anomaly': self.get_volume_anomaly(),
            'obv_trend': self.get_obv_trend(),
        }