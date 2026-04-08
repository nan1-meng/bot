# 文件路径: clients/binance_client.py
from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import List, Tuple
from .base_client import BaseClient
import logging

logger = logging.getLogger(__name__)

class BinanceClient(BaseClient):
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False, timeout: int = 10):
        self.testnet = testnet
        self.client = Client(api_key, api_secret, testnet=testnet)
        self.client.session.timeout = timeout

    def get_symbol_info(self, symbol: str) -> Tuple[float, int]:
        info = self.client.get_symbol_info(symbol)
        if not info:
            raise ValueError(f"Symbol {symbol} not found")
        filters = {f['filterType']: f for f in info['filters']}
        lot_filter = filters.get('LOT_SIZE', {})
        step = float(lot_filter.get('stepSize', '0.1'))
        price_filter = filters.get('PRICE_FILTER', {})
        tick_size = price_filter.get('tickSize', '0.01')
        quote_decimals = len(tick_size.split('.')[1]) if '.' in tick_size else 0
        return step, quote_decimals

    def get_ticker(self, symbol: str) -> float:
        ticker = self.client.get_symbol_ticker(symbol=symbol)
        return float(ticker['price'])

    def get_klines(self, symbol: str, interval: str, limit: int) -> List[List]:
        interval_map = {
            '1': Client.KLINE_INTERVAL_1MINUTE,
            '5': Client.KLINE_INTERVAL_5MINUTE,
            '15': Client.KLINE_INTERVAL_15MINUTE,
            '30': Client.KLINE_INTERVAL_30MINUTE,
            '60': Client.KLINE_INTERVAL_1HOUR,
            '1D': Client.KLINE_INTERVAL_1DAY
        }
        interval_str = interval_map.get(str(interval), Client.KLINE_INTERVAL_1MINUTE)
        klines = self.client.get_klines(symbol=symbol, interval=interval_str, limit=limit)
        result = []
        for k in klines:
            result.append([
                k[0],
                float(k[1]),
                float(k[2]),
                float(k[3]),
                float(k[4])
            ])
        return result

    def market_buy(self, symbol: str, amount_usdt: float) -> str:
        try:
            amount_formatted = round(amount_usdt, 2)
            order = self.client.order_market_buy(
                symbol=symbol,
                quoteOrderQty=amount_formatted
            )
            return str(order['orderId'])
        except BinanceAPIException as e:
            raise Exception(f"Binance buy error: {e.message}")

    def market_sell(self, symbol: str, qty: float) -> str:
        try:
            order = self.client.order_market_sell(
                symbol=symbol,
                quantity=qty
            )
            return str(order['orderId'])
        except BinanceAPIException as e:
            raise Exception(f"Binance sell error: {e.message}")

    def get_balances(self) -> List[dict]:
        account = self.client.get_account()
        balances = []
        for asset in account['balances']:
            coin = asset['asset']
            free = float(asset['free'])
            locked = float(asset['locked'])
            total = free + locked
            balances.append({
                'coin': coin,
                'availableToWithdraw': str(free),
                'walletBalance': str(total)   # 总余额
            })
        return balances

    def get_order_history(self, symbol: str, limit: int = 500, startTime: int = None) -> list:
        all_orders = []
        page_size = min(limit, 500)
        # Binance 需要分页，通过递归或循环获取
        # 简化：一次获取所有，但限制最多 1000 条
        try:
            orders = self.client.get_all_orders(symbol=symbol, limit=page_size)
            for order in orders:
                if order['status'] == 'FILLED':
                    all_orders.append({
                        'orderId': order['orderId'],
                        'side': order['side'],  # 'BUY' or 'SELL'
                        'price': float(order['price']),
                        'cumExecQty': float(order['executedQty']),
                        'cumExecValue': float(order['cummulativeQuoteQty']),
                        'timestamp': order['time'],
                        'orderStatus': order['status']
                    })
            return all_orders[:limit]
        except Exception as e:
            logger.error(f"Binance 获取历史订单异常: {e}")
            return []