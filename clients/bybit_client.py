# 文件路径: clients/bybit_client.py
from pybit.unified_trading import HTTP
from .base_client import BaseClient
import time
import logging

logger = logging.getLogger(__name__)

class BybitClient(BaseClient):
    def __init__(self, api_key, api_secret, testnet=False, timeout=10):
        self.testnet = testnet
        self.timeout = timeout
        self.session = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=api_secret,
            timeout=timeout,
            recv_window=20000
        )

    def get_symbol_info(self, symbol):
        resp = self.session.get_instruments_info(category='spot', symbol=symbol)
        if resp['retCode'] != 0:
            raise Exception(f"Bybit API error: {resp['retMsg']}")
        info = resp['result']['list'][0]
        lot_filter = info['lotSizeFilter']
        step = float(lot_filter.get('qtyStep') or lot_filter.get('stepSize') or '0.1')
        quote_precision = lot_filter.get('quotePrecision', '0.01')
        quote_decimals = len(quote_precision.split('.')[1]) if '.' in quote_precision else 0
        return step, quote_decimals

    def get_ticker(self, symbol):
        resp = self.session.get_tickers(category='spot', symbol=symbol)
        return float(resp['result']['list'][0]['bid1Price'])

    def get_klines(self, symbol, interval, limit):
        resp = self.session.get_kline(category='spot', symbol=symbol, interval=interval, limit=limit)
        return [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4])] for k in resp['result']['list']]

    def market_buy(self, symbol, amount_usdt):
        step, quote_decimals = self.get_symbol_info(symbol)
        qty = f"{amount_usdt:.{quote_decimals}f}"
        resp = self.session.place_order(
            category='spot',
            symbol=symbol,
            side='Buy',
            orderType='Market',
            qty=qty,
            marketUnit='quoteCoin',
            timeInForce='IOC'
        )
        return resp['result']['orderId']

    def market_sell(self, symbol, qty):
        step, _ = self.get_symbol_info(symbol)
        decimals = len(str(step).split('.')[1]) if '.' in str(step) else 0
        qty_str = f"{qty:.{decimals}f}"
        resp = self.session.place_order(
            category='spot',
            symbol=symbol,
            side='Sell',
            orderType='Market',
            qty=qty_str,
            timeInForce='IOC'
        )
        return resp['result']['orderId']

    def get_balances(self):
        resp = self.session.get_wallet_balance(accountType='UNIFIED')
        coins = []
        for c in resp['result']['list'][0]['coin']:
            coin_name = c['coin'].upper()  # 统一转为大写
            wallet_balance = c.get('walletBalance', '0')
            if wallet_balance == '':
                wallet_balance = '0'
            coins.append({
                'coin': coin_name,
                'availableToWithdraw': wallet_balance,
                'walletBalance': wallet_balance,
            })
        return coins

    def get_order_history(self, symbol: str, limit: int = 200, startTime: int = None) -> list:
        if startTime is None:
            startTime = int((time.time() - 90 * 24 * 3600) * 1000)
        all_orders = []
        cursor = None
        while True:
            try:
                params = {
                    "category": "spot",
                    "symbol": symbol,
                    "limit": min(limit, 200),
                    "startTime": startTime
                }
                if cursor:
                    params["cursor"] = cursor
                resp = self.session.get_order_history(**params)
                if resp['retCode'] != 0:
                    logger.error(f"Bybit 获取历史订单失败: {resp['retMsg']}")
                    break
                orders = resp['result']['list']
                if not orders:
                    break
                for order in orders:
                    if order['orderStatus'] in ('Filled', 'PartiallyFilled'):
                        all_orders.append({
                            'orderId': order['orderId'],
                            'side': order['side'],
                            'price': float(order['price']),
                            'cumExecQty': float(order['cumExecQty']),
                            'cumExecValue': float(order['cumExecValue']),
                            'timestamp': int(order['updatedTime']),
                            'orderStatus': order['orderStatus'],
                        })
                cursor = resp['result'].get('nextPageCursor')
                if not cursor or len(all_orders) >= limit:
                    break
            except Exception as e:
                logger.error(f"Bybit 获取历史订单异常: {e}")
                break
        return all_orders[:limit]