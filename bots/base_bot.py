# 文件路径: bots/base_bot.py
import threading
import time
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
                 auto_warmup: bool = True):
        self.user_id = user_id
        self.key_id = key_id
        self.symbol = symbol
        self.config = config
        self.mode_display = mode_display
        self.callback = callback
        self.db_config_id = config.get('db_id')  # 数据库配置ID

        self.client = create_client(platform, api_key, secret_key, testnet=False, timeout=10)
        try:
            self.step, self.quote_decimals = self.client.get_symbol_info(symbol)
        except Exception as e:
            raise ValueError(f"获取交易币信息失败: {symbol} - {e}")

        # 数据存储
        self._data_lock = threading.RLock()
        self.sec_prices = deque(maxlen=600)
        self.kline_prices = deque(maxlen=1000)
        self.kline_timestamps = deque(maxlen=1000)
        self.volumes = deque(maxlen=1000)
        self.kline_highs = deque(maxlen=1000)
        self.kline_lows = deque(maxlen=1000)

        self.current_minute = None
        self.minute_open = self.minute_high = self.minute_low = self.minute_close = None

        # 持仓状态
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

        # 风控管理器
        self.risk_manager = RiskManager(key_id, user_id)  # 传入 user_id

        self.running = False
        self.thread = None
        self._stop_event = threading.Event()

        if "资深" in mode_display and auto_warmup:
            self._warmup_kline()

    def start(self):
        if self.running:
            return
        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self._stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

    def _run_loop(self):
        raise NotImplementedError

    # ---------- 持仓持久化 ----------
    def _load_position_from_db(self) -> bool:
        """从数据库加载持仓信息，返回是否成功"""
        if not self.db_config_id:
            return False
        try:
            config = SymbolConfigDAO.get_by_id(self.db_config_id)
            if config and config.avg_price is not None and config.quantity is not None and config.quantity > 0:
                with self._position_lock:
                    self.position["has_position"] = True
                    self.position["qty"] = config.quantity
                    self.position["avg_price"] = config.avg_price
                    self.position["price_estimated"] = False
                    self.position["entry_time"] = time.time()
                    price = self.get_current_price()
                    if price:
                        self.position["highest_price"] = price
                self._log("系统", f"从数据库加载持仓: 数量={config.quantity:.4f}, 成本={config.avg_price:.6f}")
                return True
        except Exception as e:
            self._log("系统", f"从数据库加载持仓失败: {e}")
        return False

    def _save_position_to_db(self):
        """保存当前持仓到数据库"""
        if not self.db_config_id:
            return
        with self._position_lock:
            if self.position["has_position"]:
                SymbolConfigDAO.update_position(self.db_config_id, self.position["avg_price"], self.position["qty"])
            else:
                SymbolConfigDAO.clear_position(self.db_config_id)

    def _clear_position_in_db(self):
        """清空数据库中的持仓"""
        if self.db_config_id:
            SymbolConfigDAO.clear_position(self.db_config_id)

    # ---------- 交易所操作 ----------
    def get_current_price(self) -> Optional[float]:
        try:
            return self.client.get_ticker(self.symbol)
        except Exception as e:
            self._log("系统", f"获取价格失败: {e}")
            return None

    def market_buy(self, amount_usdt: float) -> Optional[str]:
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
            order_id = self.client.market_sell(self.symbol, qty)
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

    # ---------- 持仓管理 ----------
    def sync_position_from_balance(self):
        """从交易所余额同步持仓（优先从数据库加载）"""
        # 优先从数据库加载
        if self._load_position_from_db():
            return

        # 否则从交易所余额估算
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
                            self._log("系统", f"检测到已有持仓 {base:.4f}，从交易所加载成本价 {real_cost:.6f}")
                        else:
                            self.position["has_position"] = True
                            self.position["qty"] = base
                            self.position["avg_price"] = price
                            self.position["price_estimated"] = True
                            self.position["entry_time"] = time.time()
                            self.position["highest_price"] = price
                            self._log("系统", f"警告：检测到已有持仓 {base:.4f}，成本价已估算为 {price:.6f}")
                        # 保存到数据库
                        self._save_position_to_db()
                    else:
                        self.position["has_position"] = False
                        self.position["qty"] = 0.0
                        self._log("系统", f"小额持仓 {base:.4f} 价值 {base_value:.2f} USDT，小于最小订单额，已忽略")
            else:
                self.position["has_position"] = False

    def _get_real_cost_from_exchange(self) -> Optional[float]:
        """使用 FIFO 方式计算当前持仓的真实平均成本"""
        try:
            orders = self.client.get_order_history(self.symbol)
            if not orders:
                return None
            # 只考虑买入订单，按时间排序
            buy_orders = [o for o in orders if o.get('side') == 'Buy']
            if not buy_orders:
                return None
            # 按时间升序
            buy_orders.sort(key=lambda x: x.get('timestamp', 0))
            total_cost = 0.0
            total_qty = 0.0
            for order in buy_orders:
                total_cost += order.get('cumExecValue', 0)
                total_qty += order.get('cumExecQty', 0)
            if total_qty == 0:
                return None
            avg_price = total_cost / total_qty
            self._log("系统", f"从交易所获取 {self.symbol} 历史买入平均成本: {avg_price:.6f} (基于 {len(buy_orders)} 笔买入订单)")
            return avg_price
        except Exception as e:
            self._log("系统", f"从交易所获取成本失败: {e}")
            return None

    # ---------- K线更新 ----------
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

    # ---------- 辅助 ----------
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