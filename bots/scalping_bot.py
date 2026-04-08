# 文件路径: bots/scalping_bot.py
import time
import math
from bots.base_bot import BaseBot

class ScalpingBot(BaseBot):
    def __init__(self, platform, api_key, secret_key, symbol, config, user_id, key_id=None, key_service=None,
                 mode_display="", callback=None, risk_manager=None):
        super().__init__(platform, api_key, secret_key, symbol, config, user_id, key_id, mode_display, callback,
                         risk_manager=risk_manager)

        self.per_trade_amount = config.get("per_trade_amount")
        self.turnover_target = config.get("turnover_target")
        self.reward_amount = config.get("reward_amount", 0.0)
        sell_interval = config.get("sell_interval")
        self.sell_interval = 5.0 if sell_interval is None else sell_interval
        self.sell_on_profit = config.get("sell_on_profit", False)
        self.min_profit_pct = config.get("min_profit_pct", 0.002)
        self.max_hold_seconds = config.get("max_hold_seconds", 60)

        self.cumulative_turnover = 0.0
        self.total_buy = 0.0
        self.total_sell = 0.0
        self.total_fee = 0.0

        self.pending_sell = False
        self.pending_buy_price = 0.0
        self.pending_buy_qty = 0.0
        self.pending_buy_amount = 0.0
        self.pending_buy_time = 0

        self._last_tick_time = 0

    def _process_tick(self, price: float, now: float):
        if self.per_trade_amount is None or self.turnover_target is None:
            return
        if not self.running:
            return

        usdt, base = self.get_balances()
        remaining = self.turnover_target - self.cumulative_turnover
        if remaining <= 0:
            self.running = False
            self._cleanup()
            return

        slippage = self.config.get("slippage", 0.001)
        min_order = self.config.get("min_order_value", 5)
        fee_rate = slippage

        # 盈利卖出模式
        if self.sell_on_profit:
            if self.pending_sell and self.pending_buy_qty > 0:
                if now - self.pending_buy_time > self.max_hold_seconds:
                    self._log("系统", f"持仓超时 {self.max_hold_seconds} 秒，强制卖出")
                    raw_qty = math.floor(self.pending_buy_qty / self.step) * self.step
                    if raw_qty > 0:
                        try:
                            self.market_sell(raw_qty)
                            time.sleep(0.3)
                            final_usdt, final_base = self.get_balances()
                            actual_sold = self.pending_buy_qty - final_base
                            if actual_sold > 0:
                                sell_value = actual_sold * price
                                self.total_sell += sell_value
                                self.cumulative_turnover += sell_value
                                self.total_fee += sell_value * fee_rate
                                round_profit = sell_value - self.pending_buy_amount
                                self._log("系统", f"强制卖出成功，获得 {sell_value:.2f} USDT，本次盈亏: {round_profit:+.2f} USDT")
                            self.pending_sell = False
                            self.pending_buy_price = 0.0
                            self.pending_buy_qty = 0.0
                            self.pending_buy_amount = 0.0
                            if self.cumulative_turnover >= self.turnover_target:
                                self.running = False
                                self._cleanup()
                            return
                        except Exception as e:
                            self._log("系统", f"强制卖出失败: {e}")
                            self.pending_sell = False
                            self.pending_buy_qty = 0.0
                    else:
                        self._log("系统", "持仓小于最小交易量，无法卖出")
                        self.pending_sell = False
                    return

                required_gain = self.min_profit_pct + 2 * fee_rate
                target_price = self.pending_buy_price * (1 + required_gain)
                if price >= target_price:
                    raw_qty = math.floor(self.pending_buy_qty / self.step) * self.step
                    if raw_qty > 0:
                        try:
                            self.market_sell(raw_qty)
                            time.sleep(0.3)
                            final_usdt, final_base = self.get_balances()
                            actual_sold = self.pending_buy_qty - final_base
                            if actual_sold > 0:
                                sell_value = actual_sold * price
                                self.total_sell += sell_value
                                self.cumulative_turnover += sell_value
                                self.total_fee += sell_value * fee_rate
                                round_profit = sell_value - self.pending_buy_amount
                                self._log("系统", f"盈利卖出成功，获得 {sell_value:.2f} USDT，本次盈亏: {round_profit:+.2f} USDT")
                                if self.callback:
                                    self.callback(self.key_id, self.symbol, "更新UI", price, time.time())
                            self.pending_sell = False
                            self.pending_buy_price = 0.0
                            self.pending_buy_qty = 0.0
                            self.pending_buy_amount = 0.0
                            if self.cumulative_turnover >= self.turnover_target:
                                self.running = False
                                self._cleanup()
                            return
                        except Exception as e:
                            self._log("系统", f"盈利卖出失败: {e}")
                    else:
                        self._log("系统", f"持仓 {self.pending_buy_qty:.6f} 小于最小交易量，无法卖出")
                        self.pending_sell = False
                else:
                    return
            else:
                # 买入
                if remaining < min_order * 2:
                    min_buy_for_sell = min_order / (1 - slippage)
                    ideal_buy = remaining / (2 - slippage)
                    buy_amount = max(min_buy_for_sell, ideal_buy)
                else:
                    normal_turnover = self.per_trade_amount * (2 - slippage)
                    if remaining < normal_turnover:
                        buy_amount = remaining / (2 - slippage)
                    else:
                        buy_amount = self.per_trade_amount

                if usdt < buy_amount:
                    if base > 0:
                        base_value = base * price
                        if base_value >= min_order:
                            self._log("系统", f"USDT不足，尝试卖出持仓 {base:.6f} 换取 USDT")
                            sell_value, success = self._sell_all_base(base, price)
                            if success:
                                self.total_sell += sell_value
                                self.cumulative_turnover += sell_value
                                if self.cumulative_turnover >= self.turnover_target:
                                    self.running = False
                                    self._cleanup()
                                    return
                                usdt, base = self.get_balances()
                            else:
                                self._log("系统", "卖出失败，无法继续")
                                self.running = False
                                self._cleanup()
                                return
                        else:
                            self._log("系统", f"USDT不足且持仓价值 {base_value:.2f} 小于最小订单额，刷单停止")
                            self.running = False
                            self._cleanup()
                            return
                    else:
                        self._log("系统", f"USDT余额不足 (可用 {usdt:.2f})，刷单停止")
                        self.running = False
                        self._cleanup()
                        return

                try:
                    self.market_buy(buy_amount)
                    time.sleep(0.3)
                    new_usdt, new_base = self.get_balances()
                    actual_bought = new_base - base
                    if actual_bought > 0:
                        buy_value = actual_bought * price
                        self.total_buy += buy_value
                        self.cumulative_turnover += buy_value
                        self.total_fee += buy_value * fee_rate
                        base = new_base
                        self.pending_sell = True
                        self.pending_buy_price = price
                        self.pending_buy_qty = actual_bought
                        self.pending_buy_amount = buy_value
                        self.pending_buy_time = time.time()
                        self._log("系统", f"买入成功，获得 {actual_bought:.6f} {self.symbol.replace('USDT','')}，等待盈利卖出")
                    else:
                        self._log("系统", "买入后未检测到新增持仓，可能未成交")
                except Exception as e:
                    self._log("系统", f"买入失败: {e}")
                return

        # 原立即卖出模式
        else:
            if remaining < min_order * 2:
                min_buy_for_sell = min_order / (1 - slippage)
                ideal_buy = remaining / (2 - slippage)
                buy_amount = max(min_buy_for_sell, ideal_buy)
            else:
                normal_turnover = self.per_trade_amount * (2 - slippage)
                if remaining < normal_turnover:
                    buy_amount = remaining / (2 - slippage)
                else:
                    buy_amount = self.per_trade_amount

            if usdt < buy_amount:
                if base > 0:
                    base_value = base * price
                    if base_value >= min_order:
                        self._log("系统", f"USDT不足，尝试卖出持仓 {base:.6f} 换取 USDT")
                        sell_value, success = self._sell_all_base(base, price)
                        if success:
                            self.total_sell += sell_value
                            self.cumulative_turnover += sell_value
                            if self.cumulative_turnover >= self.turnover_target:
                                self.running = False
                                self._cleanup()
                                return
                            usdt, base = self.get_balances()
                        else:
                            self._log("系统", "卖出失败，无法继续")
                            self.running = False
                            self._cleanup()
                            return
                    else:
                        self._log("系统", f"USDT不足且持仓价值 {base_value:.2f} 小于最小订单额，刷单停止")
                        self.running = False
                        self._cleanup()
                        return
                else:
                    self._log("系统", f"USDT余额不足 (可用 {usdt:.2f})，刷单停止")
                    self.running = False
                    self._cleanup()
                    return

            try:
                self.market_buy(buy_amount)
                time.sleep(0.3)
                new_usdt, new_base = self.get_balances()
                actual_bought = new_base - base
                if actual_bought > 0:
                    buy_value = actual_bought * price
                    self.total_buy += buy_value
                    self.cumulative_turnover += buy_value
                    self.total_fee += buy_value * fee_rate
                    base = new_base
                    self._log("系统", f"买入成功，获得 {actual_bought:.6f} {self.symbol.replace('USDT','')}")
                else:
                    self._log("系统", "买入后未检测到新增持仓，可能未成交")
                    return
            except Exception as e:
                self._log("系统", f"买入失败: {e}")
                return

            if self.cumulative_turnover >= self.turnover_target:
                self.running = False
                self._cleanup()
                return

            if base <= 0:
                self._log("系统", "持仓为0，无法卖出")
                return

            raw_qty = math.floor(base / self.step) * self.step
            if raw_qty <= 0:
                self._log("系统", f"持仓 {base:.6f} 小于最小交易量 {self.step}，跳过卖出")
                return

            sell_price = self.get_current_price()
            if sell_price is None:
                return
            sell_value_check = raw_qty * sell_price
            if sell_value_check < min_order:
                self._log("系统", f"可卖数量 {raw_qty:.6f} 价值 {sell_value_check:.2f} 小于最小订单额，跳过卖出")
                return

            try:
                self.market_sell(raw_qty)
                time.sleep(0.3)
                final_usdt, final_base = self.get_balances()
                actual_sold = base - final_base
                if actual_sold > 0:
                    sell_value = actual_sold * sell_price
                    self.total_sell += sell_value
                    self.cumulative_turnover += sell_value
                    self.total_fee += sell_value * fee_rate
                    base = final_base
                    round_profit = sell_value - buy_amount
                    self._log("系统", f"卖出成功，获得约 {sell_value:.2f} USDT，本次盈亏: {round_profit:+.2f} USDT")
                    if self.callback:
                        self.callback(self.key_id, self.symbol, "更新UI", sell_price, time.time())
                else:
                    self._log("系统", "卖出后持仓未减少，可能未成交")
            except Exception as e:
                self._log("系统", f"卖出失败: {e}")
                return

            if self.cumulative_turnover >= self.turnover_target:
                self.running = False
                self._cleanup()
                return

            time.sleep(self.sell_interval)

    def _sell_all_base(self, base, price):
        if base <= 0:
            return 0.0, False
        raw_qty = math.floor(base / self.step) * self.step
        if raw_qty <= 0:
            return 0.0, False
        min_order = self.config.get("min_order_value", 5)
        expected_value = raw_qty * price
        if expected_value < min_order:
            return 0.0, False
        try:
            self.market_sell(raw_qty)
            time.sleep(0.5)
            _, new_base = self.get_balances()
            actual_sold = base - new_base
            if actual_sold > 0:
                sell_value = actual_sold * price
                fee_rate = self.config.get("slippage", 0.001)
                self.total_fee += sell_value * fee_rate
                return sell_value, True
            else:
                return 0.0, False
        except Exception as e:
            self._log("系统", f"卖出异常: {e}")
            return 0.0, False

    def _cleanup(self):
        try:
            usdt, base = self.get_balances()
            if base > 0:
                price = self.get_current_price()
                if price:
                    base_value = base * price
                    if base_value > 1.0:
                        min_order = self.config.get("min_order_value", 5)
                        if base_value < min_order:
                            buy_amount = min_order
                            if usdt >= buy_amount:
                                self.market_buy(buy_amount)
                                time.sleep(1)
                                new_usdt, new_base = self.get_balances()
                                actual_bought = new_base - base
                                if actual_bought > 0:
                                    buy_value = actual_bought * price
                                    self.total_buy += buy_value
                                    self.cumulative_turnover += buy_value
                                    base = new_base
                                    raw_qty = math.floor(base / self.step) * self.step
                                    if raw_qty > 0:
                                        sell_price = self.get_current_price()
                                        if sell_price:
                                            sell_value_check = raw_qty * sell_price
                                            if sell_value_check >= min_order:
                                                self.market_sell(raw_qty)
                                                time.sleep(1)
                                                final_usdt, final_base = self.get_balances()
                                                actual_sold = base - final_base
                                                if actual_sold > 0:
                                                    sell_value = actual_sold * sell_price
                                                    self.total_sell += sell_value
                                                    self.cumulative_turnover += sell_value
                                                    self._log("系统", f"残留持仓处理：买入 {buy_amount:.2f} USDT 后卖出，获得 {sell_value:.2f} USDT")
                        else:
                            if base_value >= min_order:
                                raw_qty = math.floor(base / self.step) * self.step
                                if raw_qty > 0:
                                    sell_price = self.get_current_price()
                                    if sell_price and raw_qty * sell_price >= min_order:
                                        self.market_sell(raw_qty)
                                        time.sleep(1)
                                        final_usdt, final_base = self.get_balances()
                                        actual_sold = base - final_base
                                        if actual_sold > 0:
                                            sell_value = actual_sold * sell_price
                                            self.total_sell += sell_value
                                            self.cumulative_turnover += sell_value
                                            self._log("系统", f"残留持仓处理：直接卖出，获得 {sell_value:.2f} USDT")
        except Exception as e:
            self._log("系统", f"残留持仓处理异常: {e}")

        net_pnl = self.total_sell - self.total_buy
        total_wear = self.total_buy - self.total_sell
        final_change = net_pnl + self.reward_amount
        self._log("系统", f"刷单停止，累计交易额: {self.cumulative_turnover:.2f} USDT")
        self._log("系统", f"总买入: {self.total_buy:.2f}, 总卖出: {self.total_sell:.2f}")
        self._log("系统", f"总磨损: {total_wear:.2f} USDT")
        self._log("系统", f"买卖净盈亏: {net_pnl:+.2f} USDT, 奖励: +{self.reward_amount:.2f} USDT")
        self._log("系统", f"最终余额变化: {final_change:+.2f} USDT")

        if self.key_service:
            self.key_service.stop_bot(self.key_id, self.symbol)

    def _run_loop(self):
        pass