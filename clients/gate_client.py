# 文件路径: clients/gate_client.py
import time
from .base_client import BaseClient

class GateClient(BaseClient):
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False, timeout: int = 10):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.timeout = timeout
    def get_symbol_info(self, symbol):
        return 0.000001, 6
    def get_ticker(self, symbol):
        return 1.0
    def get_ticker_price(self, symbol):
        return self.get_ticker(symbol)
    def get_klines(self, symbol, interval='1', limit=100):
        now = int(time.time())
        data=[]
        base=1.0
        for i in range(limit):
            price = base + i*0.0004
            data.append([ (now-(limit-i)*60)*1000, price, price*1.002, price*0.998, price*1.001, 100+i ])
        return data
    def market_buy(self, symbol, amount_usdt):
        return f'gate_buy_{int(time.time()*1000)}'
    def market_sell(self, symbol, qty):
        return f'gate_sell_{int(time.time()*1000)}'
    def get_balances(self):
        return [{'coin':'USDT','walletBalance':'0','availableToWithdraw':'0'}]
    def get_order_history(self, symbol, limit=100, startTime=None):
        return []
    def fetch_recent_trades_for_reconcile(self, symbol: str, since_ms: int = 0):
        return []
