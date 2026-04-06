# 文件路径: core/market_data_cache.py
import threading
from typing import Dict
from core.market_features import MarketFeatures

class MarketDataCache:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._features: Dict[str, MarketFeatures] = {}
        self._lock = threading.RLock()

    def get_or_create(self, symbol: str) -> MarketFeatures:
        with self._lock:
            if symbol not in self._features:
                self._features[symbol] = MarketFeatures(symbol)
            return self._features[symbol]

    def update_trade(self, symbol: str, trade: Dict):
        features = self.get_or_create(symbol)
        features.update_trade(trade)

    def get_features(self, symbol: str) -> Dict[str, float]:
        features = self.get_or_create(symbol)
        return features.get_features()