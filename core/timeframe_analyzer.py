# 文件路径: core/timeframe_analyzer.py
from typing import Dict, List, Optional
from core.indicators import Indicators

class TimeframeAnalyzer:
    """多时间框架趋势分析（1h、4h、1d）"""
    def __init__(self):
        self.ind = Indicators()
        self.cache: Dict[str, Dict[str, str]] = {}  # {symbol: {"1h": "bull", "4h": "bear", ...}}

    def get_trend(self, symbol: str, klines: List[List], timeframe: str) -> str:
        """
        根据K线数据判断趋势
        klines: 列表格式 [[timestamp, open, high, low, close], ...]
        timeframe: '1h', '4h', '1d'
        返回 'bull', 'bear', 'neutral'
        """
        if len(klines) < 50:
            return 'neutral'
        closes = [k[4] for k in klines]
        sma20 = self.ind.sma(closes, 20)
        sma50 = self.ind.sma(closes, 50)
        if sma20 is None or sma50 is None:
            return 'neutral'
        if sma20 > sma50 * 1.01:
            return 'bull'
        elif sma20 < sma50 * 0.99:
            return 'bear'
        else:
            return 'neutral'

    def update_cache(self, symbol: str, klines_1h: List[List], klines_4h: List[List], klines_1d: List[List]):
        """更新缓存的趋势状态"""
        self.cache[symbol] = {
            '1h': self.get_trend(symbol, klines_1h, '1h'),
            '4h': self.get_trend(symbol, klines_4h, '4h'),
            '1d': self.get_trend(symbol, klines_1d, '1d')
        }

    def is_bullish_aligned(self, symbol: str) -> bool:
        """多时间框架是否一致看多（1h、4h、1d 都是 bull）"""
        if symbol not in self.cache:
            return False
        trends = self.cache[symbol]
        return trends['1h'] == 'bull' and trends['4h'] == 'bull' and trends['1d'] == 'bull'

    def get_higher_trend(self, symbol: str) -> str:
        """返回较高时间框架的趋势（优先级 1d > 4h > 1h）"""
        if symbol not in self.cache:
            return 'neutral'
        if self.cache[symbol]['1d'] != 'neutral':
            return self.cache[symbol]['1d']
        if self.cache[symbol]['4h'] != 'neutral':
            return self.cache[symbol]['4h']
        return self.cache[symbol]['1h']