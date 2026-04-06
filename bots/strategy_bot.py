# 文件路径: bots/strategy_bot.py
import time
import math
from bots.base_bot import BaseBot
from core.indicators import Indicators

class StrategyBot(BaseBot):
    def __init__(self, platform, api_key, secret_key, symbol, config, user_id, key_id=None, key_service=None,
                 mode_display="", callback=None):
        super().__init__(platform, api_key, secret_key, symbol, config, user_id, key_id, mode_display, callback)
        self.indicators = Indicators()

    def _run_loop(self):
        self.running = True
        last_minute_price = None
        last_check_time = time.time()
        is_fast_sell = self.config.get("fast_sell", False)
        add_buy_drop = self.config.get("add_buy_drop", 0.02)
        min_trade_interval = self.config.get("min_trade_interval", 60)

        self.sync_position_from_balance()

        while self.running and not self._stop_event.is_set():
            try:
                price = self.get_current_price()
                if price is None:
                    time.sleep(1)
                    continue

                now = time.time()
                self.update_kline(price, now)

                if self.current_minute is not None and len(self.kline_prices) > 0:
                    minute_close = self.kline_prices[-1]
                    rsi = self.indicators.rsi(list(self.kline_prices), self.config.get("rsi_period", 14))
                    trend = self.trend_filter() if self.config.get("use_trend_filter", True) else "neutral"
                    usdt, base_balance = self.get_balances()

                    # 补仓检查（每分钟）
                    if now - last_check_time >= 60:
                        last_check_time = now
                        if last_minute_price is not None and last_minute_price != 0:
                            drop_pct = (last_minute_price - minute_close) / last_minute_price
                            if drop_pct >= add_buy_drop:
                                if self.position["has_position"] and usdt >= self.config.get("min_order_value", 5):
                                    max_buy = self.config.get("max_buy_amount")
                                    if max_buy is None or max_buy > 1e9:
                                        buy_amt = usdt * self.config.get("add_buy_ratio", 0.3)
                                    else:
                                        buy_amt = min(usdt * self.config.get("add_buy_ratio", 0.3), max_buy)
                                    if buy_amt < self.config.get("min_order_value", 5):
                                        buy_amt = self.config.get("min_order_value", 5)
                                    if buy_amt > usdt:
                                        buy_amt = usdt
                                    if buy_amt >= self.config.get("min_order_value", 5):
                                        try:
                                            self.market_buy(buy_amt)
                                            time.sleep(2)
                                            new_balances = self.get_balances()
                                            new_base = new_balances[1]
                                            with self._position_lock:
                                                if new_base > self.position["qty"]:
                                                    if self.position["avg_price"] == 0 or self.position["qty"] == 0:
                                                        self.position["avg_price"] = buy_amt / new_base
                                                    else:
                                                        total_cost = self.position["avg_price"] * self.position["qty"] + buy_amt
                                                        total_qty = new_base
                                                        if total_qty != 0:
                                                            self.position["avg_price"] = total_cost / total_qty
                                                    self.position["qty"] = new_base
                                                    self.position["last_trade_time"] = now
                                                    self.position["price_estimated"] = False
                                                    self._log("补仓", f"{self.symbol} 补仓 {buy_amt:.2f} USDT", price)
                                        except Exception as e:
                                            self._log("系统", f"补仓失败: {e}")
                        last_minute_price = minute_close

                    # 首次买入
                    if not self.position["has_position"]:
                        if now - self.position["last_trade_time"] >= min_trade_interval:
                            rsi_cond = (not self.config.get("use_rsi_threshold", True)) or (rsi is not None and rsi < self.config.get("rsi_oversold", 30))
                            if rsi_cond:
                                if self.config.get("use_trend_filter", True) and trend == "bear":
                                    pass
                                else:
                                    if usdt >= self.config.get("min_order_value", 5):
                                        max_buy = self.config.get("max_buy_amount")
                                        if max_buy is None or max_buy > 1e9:
                                            buy_amt = usdt * self.config.get("buy_ratio", 0.5)
                                        else:
                                            buy_amt = min(usdt * self.config.get("buy_ratio", 0.5), max_buy)
                                        if buy_amt < self.config.get("min_order_value", 5):
                                            buy_amt = self.config.get("min_order_value", 5)
                                        if buy_amt > usdt:
                                            buy_amt = usdt
                                        if buy_amt >= self.config.get("min_order_value", 5):
                                            try:
                                                self.market_buy(buy_amt)
                                                time.sleep(2)
                                                new_balances = self.get_balances()
                                                new_base = new_balances[1]
                                                if new_base > 0:
                                                    with self._position_lock:
                                                        self.position["has_position"] = True
                                                        self.position["qty"] = new_base
                                                        self.position["avg_price"] = buy_amt / new_base
                                                        self.position["last_trade_time"] = now
                                                        self.position["entry_time"] = now
                                                        self.position["price_estimated"] = False
                                                    self._log("买入", f"{self.symbol} 买入 {buy_amt:.2f} USDT", price)
                                            except Exception as e:
                                                self._log("系统", f"买入失败: {e}")

                    # 卖出逻辑
                    else:
                        with self._position_lock:
                            if self.position["avg_price"] == 0:
                                continue
                            if self.position["price_estimated"]:
                                position_value = self.position["qty"] * price
                                min_order = self.config.get("min_order_value", 5)
                                if position_value < min_order:
                                    continue

                            if now - self.position["last_trade_time"] >= min_trade_interval:
                                sell_price_with_slippage = minute_close * (1 - self.config.get("slippage", 0.001))
                                profit_pct = (sell_price_with_slippage - self.position["avg_price"]) / self.position["avg_price"]
                                position_value = self.position["qty"] * minute_close

                                if is_fast_sell:
                                    if sell_price_with_slippage > self.position["avg_price"]:
                                        raw_qty = math.floor(self.position["qty"] / self.step) * self.step
                                        if raw_qty > 0:
                                            if position_value < self.config.get("min_order_value", 5) or raw_qty * minute_close >= self.config.get("min_order_value", 5):
                                                try:
                                                    self.market_sell(raw_qty)
                                                    self.position["has_position"] = False
                                                    self.position["qty"] = 0.0
                                                    self.position["last_trade_time"] = now
                                                    self.position["price_estimated"] = False
                                                    self._log("卖出", f"{self.symbol} 卖出 {raw_qty:.4f} 个", minute_close)
                                                except Exception as e:
                                                    self._log("系统", f"卖出失败: {e}")
                                    continue

                                should_sell = False
                                rsi_cond = (not self.config.get("use_rsi_threshold", True)) or (rsi is not None and rsi > self.config.get("rsi_overbought", 70))
                                if profit_pct >= self.config.get("take_profit", 0.005):
                                    if rsi_cond or (self.config.get("use_trend_filter", True) and trend == "bear"):
                                        should_sell = True
                                elif profit_pct <= self.config.get("stop_loss", -0.02):
                                    should_sell = True

                                if should_sell:
                                    raw_qty = math.floor(self.position["qty"] / self.step) * self.step
                                    if raw_qty > 0:
                                        if position_value < self.config.get("min_order_value", 5) or raw_qty * minute_close >= self.config.get("min_order_value", 5):
                                            try:
                                                self.market_sell(raw_qty)
                                                self.position["has_position"] = False
                                                self.position["qty"] = 0.0
                                                self.position["last_trade_time"] = now
                                                self.position["price_estimated"] = False
                                                self._log("卖出", f"{self.symbol} 卖出 {raw_qty:.4f} 个", minute_close)
                                            except Exception as e:
                                                self._log("系统", f"卖出失败: {e}")

                    if self.callback:
                        self.callback(self.key_id, self.symbol, "更新UI", price, now)

            except Exception as e:
                self._log("系统", f"交易线程异常: {e}")
                time.sleep(1)

    def trend_filter(self) -> str:
        sma50 = self.indicators.sma(list(self.kline_prices), self.config.get("sma_short", 50))
        sma200 = self.indicators.sma(list(self.kline_prices), self.config.get("sma_long", 200))
        if sma50 is None or sma200 is None:
            return "neutral"
        return "bull" if sma50 > sma200 else "bear" if sma50 < sma200 else "neutral"