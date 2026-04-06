# 文件路径: clients/base_client.py
from abc import ABC, abstractmethod

class BaseClient(ABC):
    @abstractmethod
    def get_symbol_info(self, symbol):
        pass

    @abstractmethod
    def get_ticker(self, symbol):
        pass

    @abstractmethod
    def get_klines(self, symbol, interval, limit):
        pass

    @abstractmethod
    def market_buy(self, symbol, amount_usdt):
        pass

    @abstractmethod
    def market_sell(self, symbol, qty):
        pass

    @abstractmethod
    def get_balances(self):
        pass

    # 可选方法，子类可实现（Bybit 需要）
    def get_order_history(self, symbol, limit=100, startTime=None):
        raise NotImplementedError