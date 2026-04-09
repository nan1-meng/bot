# ============================================================
# 文件: bots/base_bot.py
# 说明: 机器人基类，提供通用持仓管理、余额获取、K线更新、交易执行
# ============================================================

import threading
import time
import math
from collections import deque
from typing import Callable, Optional, Dict, Any
from clients import create_client
from core.risk_manager import RiskManager
import logging
from dao.symbol_config_dao import SymbolConfigDAO

logger = logging.getLogger(__name__)


class BaseBot:
    def __init__(self, platform: str, api_key: str, secret_key: str, symbol: str, config: Dict[str, Any],
                 user_id: int, key_id: int, mode_display: str = "", callback: Optional[Callable] = None,
                 auto_warmup: bool = True, risk_manager: RiskManager = None):
        self.user_id = user_id
        self.key_id = key_id
        self.symbol = symbol
        self.config = config
        self.mode_display = mode_display
        self.callback = callback
        self.db_config_id = config.get('db_id')
        self.key_service = None  # 会在外部设置

        self.client = create_client(platform, api_key, secret_key, testnet=False, timeout=10)
        try:
            self.step, self.quote_decimals = self.client.get_symbol_info(symbol)
        except Exception as e:
            raise ValueError(f"获取交易币信息失败: {symbol} - {e}")

        self._data_lock = threading.RLock()
        self.sec_prices = deque(maxlen=600)
        self.kline_prices = deque(maxlen=1000)
        self.kline_timestamps = deque(maxlen=1000)
        self.volumes = deque(maxlen=1000)
        self.kline_highs = deque(maxlen=1000)
        self.kline_lows = deque(maxlen=1000)

        self.current_minute = None
        self.minute_open = self.minute_high = self.minute_low = self.minute_close = None

        self._position_lock = threading.RLock()
        self.position = {
            "has_position": False,
            "qty": 0.0,
            "avg_price": 0.0,
            "price_estimated": False,
            "last_trade_time": 0,
            "entry_time": 0,
            "highest_price": 0.0,
            "lowest_price": 0.0,
        }

        if risk_manager is not None:
            self.risk_manager = risk_manager
        else:
            self.risk_manager = RiskManager(key_id, user_id)

        self.running = False
        self._external_mode = False
        self._stop_event = threading.Event()
        self._last_sync_time = 0

        # 新增：补仓失败冷却
        self._add_fail_until = 0
        # 新增：卖出失败冷却（针对残仓无法卖出）
        self._sell_fail_until = 0
        self._sell_fail_count = 0
        self.MAX_SELL_FAIL = 3
        self.SELL_FAIL_COOLDOWN = 300  # 5分钟

        if "资深" in mode_display and auto_warmup:
            self._warmup_kline()

    def start(self):
        if self._external_mode:
            self.running = True
            return
        if self.running:
            return
        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if not self._external_mode:
            self._stop_event.set()
            if hasattr(self, 'thread') and self.thread and self.thread.is_alive():
                self.thread.join(timeout=2)

    def _run_loop(self):
        raise NotImplementedError

    def on_tick(self, price: float, timestamp: float):
        if not self.running:
            return
        self._process_tick(price, timestamp)

    def _process_tick(self, price: float, timestamp: float):
        raise NotImplementedError

    def _after_sell(self, pnl: float, exit_reason: str, hold_seconds: int,
                    market_state: str, entry_score: float = None,
                    add_records: list = None, price: float = None, quantity: float = None):
        if hasattr(self.risk_manager, 'online_learner') and self.risk_manager.online_learner:
            try:
                from collections import namedtuple
                trade_data = {
                    'id': None,
                    'symbol': self.symbol,
                    'side': 'sell',
                    'pnl': pnl,
                    'exit_reason': exit_reason,
                    'market_state': market_state,
                    'add_records': add_records or [],
                    'price': price or self.get_current_price(),
                    'quantity': quantity or 0,
                    'hold_seconds': hold_seconds,
                    'entry_score': entry_score,
                    'is_manual': False
                }
                TradeObj = namedtuple('TradeObj', trade_data.keys())
                trade = TradeObj(**trade_data)
                self.risk_manager.online_learner.on_trade_complete(trade)
            except Exception as e:
                self._log("系统", f"学习器回调失败: {e}")

    def _load_position_from_db(self) -> bool:
        if not self.db_config_id:
            return False
        try:
            config = SymbolConfigDAO.get_by_id(self.db_config_id)
            if config and config.quantity is not None and config.quantity > 0 and config.avg_price is not None:
                _, base = self.get_balances()
                db_qty = float(config.quantity)
                # 对账：若数据库数量与交易所实际持仓相差超过1%，可能发生了手动交易，重置学习数据
                if abs(db_qty - base) > max(0.0001, base * 0.01):
                    self._log("系统", f"检测到持仓与数据库记录不符 (DB:{db_qty:.4f}, 实际:{base:.4f})，可能发生手动交易，重置学习状态")
                    self._clear_position_in_db()
                    if self.risk_manager:
                        self.risk_manager.reset_symbol_health(self.symbol)
                    return False
                with self._position_lock:
                    self.position["has_position"] = True
                    self.position["qty"] = db_qty
                    self.position["avg_price"] = float(config.avg_price)
                    self.position["price_estimated"] = False
                    self.position["entry_time"] = time.time()
                    price = self.get_current_price()
                    if price:
                        self.position["highest_price"] = price
                return True
        except Exception as e:
            self._log("系统", f"从数据库加载持仓失败: {e}")
        return False

    def _save_position_to_db(self):
        if not self.db_config_id:
            return
        with self._position_lock:
            if self.position["has_position"] and self.position["qty"] > 0:
                SymbolConfigDAO.update_position(self.db_config_id, self.position["avg_price"], self.position["qty"])
            else:
                SymbolConfigDAO.clear_position(self.db_config_id)

    def _clear_position_in_db(self):
        if not self.db_config_id:
            return
        SymbolConfigDAO.clear_position(self.db_config_id)

    def get_current_price(self) -> Optional[float]:
        try:
            return self.client.get_ticker(self.symbol)
        except Exception as e:
            self._log("系统", f"获取价格失败: {e}")
            return None

    def market_buy(self, amount_usdt: float) -> Optional[str]:
        if amount_usdt < 5.0:
            self._log("系统", f"买入金额 {amount_usdt:.2f} USDT 低于最小限额 5 USDT")
            return None
        if not self.risk_manager.can_buy(self.symbol, amount_usdt):
            self._log("风控", f"买入被拒绝：{self.risk_manager.get_last_reason()}")
            return None
        try:
            order_id = self.client.market_buy(self.symbol, amount_usdt)
            self._log("系统", f"买入订单成功: {order_id}")
            return order_id
        except Exception as e:
            self._log("系统", f"买入异常: {e}")
            return None

    def market_sell(self, qty: float) -> Optional[str]:
        if not self.risk_manager.can_sell(self.symbol, qty):
            self._log("风控", f"卖出被拒绝：{self.risk_manager.get_last_reason()}")
            return None
        try:
            step_str = str(self.step).rstrip('0')
            if '.' in step_str:
                decimals = len(step_str.split('.')[1])
            else:
                decimals = 0
            formatted_qty = round(qty, decimals)
            if formatted_qty <= 0:
                self._log("系统", f"卖出数量 {qty} 格式化后为0，跳过")
                return None
            order_id = self.client.market_sell(self.symbol, formatted_qty)
            self._log("系统", f"卖出订单成功: {order_id}")
            return order_id
        except Exception as e:
            self._log("系统", f"卖出异常: {e}")
            return None

    def get_balances(self) -> tuple[float, float]:
        try:
            coins = self.client.get_balances()
            usdt = 0.0
            base_coin = self.symbol.replace("USDT", "")
            base = 0.0
            for coin in coins:
                if coin["coin"] == "USDT":
                    available = coin.get("availableToWithdraw", "")
                    if available == "":
                        available = coin.get("walletBalance", "0")
                    usdt = float(available) if available else 0.0
                elif coin["coin"] == base_coin:
                    available = coin.get("availableToWithdraw", "")
                    if available == "":
                        available = coin.get("walletBalance", "0")
                    base = float(available) if available else 0.0
            return usdt, base
        except Exception as e:
            self._log("系统", f"获取余额失败: {e}")
            return 0.0, 0.0

    def sync_position_from_balance(self):
        now = time.time()
        if now - self._last_sync_time < 5:
            return
        self._last_sync_time = now

        if self._load_position_from_db():
            return

        usdt, base = self.get_balances()
        with self._position_lock:
            if base > 0:
                price = self.get_current_price()
                if price:
                    min_order = self.config.get("min_order_value", 5)
                    base_value = base * price
                    if base_value >= min_order:
                        real_cost = self._get_real_cost_from_exchange()
                        if real_cost is not None:
                            self.position["has_position"] = True
                            self.position["qty"] = base
                            self.position["avg_price"] = real_cost
                            self.position["price_estimated"] = False
                            self.position["entry_time"] = time.time()
                            self.position["highest_price"] = price
                            self._save_position_to_db()
                        else:
                            self.position["has_position"] = True
                            self.position["qty"] = base
                            self.position["avg_price"] = price
                            self.position["price_estimated"] = True
                            self.position["entry_time"] = time.time()
                            self.position["highest_price"] = price
                            self._save_position_to_db()
                            self._log("系统", f"检测到已有持仓 {base:.4f}，无法获取真实成本，使用当前价 {price:.6f} 估算")
                    else:
                        self.position["has_position"] = False
                        self.position["qty"] = 0.0
                        self._clear_position_in_db()
            else:
                self.position["has_position"] = False
                self.position["qty"] = 0.0
                self._clear_position_in_db()

    def _get_real_cost_from_exchange(self) -> Optional[float]:
        try:
            orders = self.client.get_order_history(self.symbol)
            if not orders:
                return None
            buy_orders = []
            for order in orders:
                side = order.get('side', '')
                if side in ('Buy', 'BUY', '买入'):
                    buy_orders.append(order)
            if not buy_orders:
                return None
            total_cost = 0.0
            total_qty = 0.0
            for order in buy_orders:
                qty = float(order.get('cumExecQty') or order.get('executedQty') or order.get('origQty') or 0)
                value = float(order.get('cumExecValue') or order.get('cummulativeQuoteQty') or order.get('quoteQty') or 0)
                if value == 0 and 'price' in order and qty > 0:
                    value = float(order.get('price', 0)) * qty
                total_cost += value
                total_qty += qty
            if total_qty == 0:
                return None
            avg_price = total_cost / total_qty
            return avg_price
        except Exception as e:
            self._log("系统", f"从交易所获取成本失败: {e}")
            return None

    def update_kline(self, price: float, timestamp: float):
        minute_ts = int(timestamp // 60) * 60
        if self.current_minute != minute_ts:
            if self.current_minute is not None and self.minute_close is not None:
                self.kline_prices.append(self.minute_close)
                self.kline_timestamps.append(self.current_minute)
                if self.minute_high is not None and self.minute_low is not None:
                    self.kline_highs.append(self.minute_high)
                    self.kline_lows.append(self.minute_low)
            self.current_minute = minute_ts
            self.minute_open = price
            self.minute_high = price
            self.minute_low = price
            self.minute_close = price
        else:
            self.minute_high = max(self.minute_high, price)
            self.minute_low = min(self.minute_low, price)
            self.minute_close = price

    def _warmup_kline(self, minutes=30):
        try:
            self._log("系统", f"正在拉取历史K线数据预热({minutes}分钟)...")
            klines = self.client.get_klines(self.symbol, interval='1', limit=minutes)
            for k in klines:
                timestamp = k[0] // 1000
                close_price = k[4]
                high = k[2]
                low = k[3]
                volume = float(k[5]) if len(k) > 5 else 0
                self.kline_prices.append(close_price)
                self.kline_timestamps.append(timestamp)
                self.kline_highs.append(high)
                self.kline_lows.append(low)
                self.volumes.append(volume)
            self._log("系统", f"预热完成，已加载 {len(self.kline_prices)} 条1分钟K线")
        except Exception as e:
            self._log("系统", f"预热异常: {e}")

    def _format_amount(self, amount: float) -> str:
        return f"{amount:.{self.quote_decimals}f}"

    def _format_qty(self, qty: float) -> str:
        step_str = str(self.step).rstrip('0')
        if '.' in step_str:
            decimals = len(step_str.split('.')[1])
        else:
            decimals = 0
        return f"{qty:.{decimals}f}"

    def _log(self, signal_type: str, msg: str, price: float = 0):
        if self.callback:
            self.callback(self.key_id, self.symbol, signal_type, price, time.time(), msg=msg)