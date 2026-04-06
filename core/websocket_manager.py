# 文件路径: core/websocket_manager.py
import threading
import time
import json
import websocket
from typing import Dict, Callable, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self, platform: str, api_key: str = None, api_secret: str = None):
        self.platform = platform.lower()
        self.api_key = api_key
        self.api_secret = api_secret
        self.ws = None
        self.running = False
        self.subscriptions = {}  # {symbol: {'kline': callback, 'trade': callback}}
        self._pending_subscriptions: List[Tuple[str, str, Optional[str]]] = []
        self._connected = False
        self._lock = threading.RLock()
        self._thread = None
        self._stop = threading.Event()
        self._reconnect_delay = 5
        self._max_reconnect_delay = 60

    def start(self):
        if self.running:
            return
        self.running = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        self._stop.set()
        if self.ws:
            self.ws.close()
        if self._thread:
            self._thread.join(timeout=2)

    def subscribe_kline(self, symbol: str, callback: Callable, interval: str = '1'):
        with self._lock:
            if symbol not in self.subscriptions:
                self.subscriptions[symbol] = {'kline': None, 'trade': None}
            self.subscriptions[symbol]['kline'] = callback
        if self._connected:
            self._send_subscribe(symbol, 'kline', interval)
        else:
            self._pending_subscriptions.append((symbol, 'kline', interval))

    def subscribe_trade(self, symbol: str, callback: Callable):
        with self._lock:
            if symbol not in self.subscriptions:
                self.subscriptions[symbol] = {'kline': None, 'trade': None}
            self.subscriptions[symbol]['trade'] = callback
        if self._connected:
            self._send_subscribe(symbol, 'trade')
        else:
            self._pending_subscriptions.append((symbol, 'trade', None))

    def _send_subscribe(self, symbol: str, channel: str, interval: str = '1'):
        if not self.ws or not self.running or not self._connected:
            return
        try:
            if self.platform == 'bybit':
                if channel == 'kline':
                    topic = f"kline.{interval}.{symbol}"
                else:
                    topic = f"publicTrade.{symbol}"
                msg = {"op": "subscribe", "args": [topic]}
                self.ws.send(json.dumps(msg))
            elif self.platform == 'binance':
                if channel == 'kline':
                    stream = f"{symbol.lower()}@kline_{interval}m"
                else:
                    stream = f"{symbol.lower()}@trade"
                msg = {"method": "SUBSCRIBE", "params": [stream], "id": 1}
                self.ws.send(json.dumps(msg))
        except Exception as e:
            logger.error(f"发送订阅失败 {symbol}/{channel}: {e}")

    def _run(self):
        url = self._get_url()
        delay = self._reconnect_delay
        while self.running and not self._stop.is_set():
            try:
                self.ws = websocket.WebSocketApp(url,
                                                 on_open=self._on_open,
                                                 on_message=self._on_message,
                                                 on_error=self._on_error,
                                                 on_close=self._on_close)
                self.ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as e:
                logger.error(f"WebSocket 连接异常: {e}")
            if not self.running or self._stop.is_set():
                break
            logger.info(f"WebSocket 断开，{delay}秒后重连...")
            time.sleep(delay)
            delay = min(delay * 2, self._max_reconnect_delay)

    def _get_url(self):
        if self.platform == 'bybit':
            return "wss://stream.bybit.com/v5/public/spot"
        elif self.platform == 'binance':
            return "wss://stream.binance.com:9443/ws"
        else:
            raise ValueError(f"Unsupported platform: {self.platform}")

    def _on_open(self, ws):
        logger.info(f"WebSocket connected for {self.platform}")
        self._connected = True
        # 发送所有待订阅请求
        for symbol, channel, interval in self._pending_subscriptions:
            if channel == 'kline':
                self._send_subscribe(symbol, 'kline', interval)
            else:
                self._send_subscribe(symbol, 'trade')
        self._pending_subscriptions.clear()
        # 同时重新订阅之前已经注册的（以防断开重连）
        with self._lock:
            for symbol, subs in self.subscriptions.items():
                if subs.get('kline'):
                    self._send_subscribe(symbol, 'kline')
                if subs.get('trade'):
                    self._send_subscribe(symbol, 'trade')

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if self.platform == 'bybit':
                self._handle_bybit_message(data)
            else:
                self._handle_binance_message(data)
        except Exception as e:
            logger.error(f"WebSocket message error: {e}")

    def _handle_bybit_message(self, data):
        if 'topic' in data:
            topic = data['topic']
            if topic.startswith('kline'):
                parts = topic.split('.')
                symbol = parts[-1]
                kline = data['data']
                with self._lock:
                    if symbol in self.subscriptions and self.subscriptions[symbol]['kline']:
                        self.subscriptions[symbol]['kline'](kline)
            elif topic.startswith('publicTrade'):
                parts = topic.split('.')
                symbol = parts[-1]
                trades = data['data']
                with self._lock:
                    if symbol in self.subscriptions and self.subscriptions[symbol]['trade']:
                        self.subscriptions[symbol]['trade'](trades)

    def _handle_binance_message(self, data):
        if 'stream' in data:
            stream = data['stream']
            if '@kline' in stream:
                symbol = stream.split('@')[0].upper()
                kline = data['data']['k']
                with self._lock:
                    if symbol in self.subscriptions and self.subscriptions[symbol]['kline']:
                        self.subscriptions[symbol]['kline'](kline)
            elif '@trade' in stream:
                symbol = stream.split('@')[0].upper()
                trade = data['data']
                with self._lock:
                    if symbol in self.subscriptions and self.subscriptions[symbol]['trade']:
                        self.subscriptions[symbol]['trade'](trade)

    def _on_error(self, ws, error):
        logger.warning(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        logger.info(f"WebSocket closed (code: {close_status_code})")
        self._connected = False