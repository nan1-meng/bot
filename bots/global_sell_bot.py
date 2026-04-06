# 文件路径: bots/global_sell_bot.py
import time
import math
from .base_bot import BaseBot
from services.trade_service import record_trade

class GlobalSellBot(BaseBot):
    def __init__(self, platform, api_key, secret_key, symbol, config, user_id, key_id=None, key_service=None, mode_display="", callback=None):
        super().__init__(platform, api_key, secret_key, symbol, config, user_id, key_id, "全局卖出", callback)
        self.key_service = key_service
        self.take_profit_levels = [0.005, 0.01, 0.02]
        self.sell_ratios = [0.3, 0.3, 0.4]
        self.trailing_stop = config.get("trailing_stop", 0.01)
        self.stop_loss = config.get("stop_loss", -0.02)
        self.max_hold_hours = config.get("max_hold_hours", 24)
        self.last_heartbeat = 0
        self.min_order_value = config.get("min_order_value", 5.0)

    def _run_loop(self):
        self.running = True
        self.entry_time = time.time()
        self.highest_price_since_entry = self.position['avg_price']

        price = self.get_current_price()
        if price and self.callback:
            self.callback(self.key_id, self.symbol, "更新UI", price, time.time())

        while self.running and not self._stop_event.is_set():
            now = time.time()
            if now - self.last_heartbeat >= 10:
                self.last_heartbeat = now
                self._log("系统", f"{self.symbol} 全局模式心跳")
                price = self.get_current_price()
                if price and self.callback:
                    self.callback(self.key_id, self.symbol, "更新UI", price, now)

            try:
                price = self.get_current_price()
                if price is None:
                    time.sleep(1)
                    continue

                if price > self.highest_price_since_entry:
                    self.highest_price_since_entry = price

                avg_price = self.position['avg_price'] if self.position['avg_price'] is not None else 0
                if avg_price != 0:
                    gross_profit_pct = (price - avg_price) / avg_price
                    fee_rate = self.config.get("slippage", 0.001)
                    # 净盈亏百分比（扣除买卖双边的滑点/手续费估算）
                    net_profit_pct = gross_profit_pct - fee_rate * 2
                else:
                    gross_profit_pct = 0
                    net_profit_pct = 0

                profit_pct = net_profit_pct

                # 重新获取实时持仓（防止卖出后不同步）
                self.sync_position_from_balance()
                with self._position_lock:
                    current_qty = self.position["qty"]
                if current_qty <= 0:
                    self._log("系统", f"{self.symbol} 无持仓，退出")
                    break

                raw_qty = math.floor(current_qty / self.step) * self.step
                if raw_qty <= 0:
                    time.sleep(1)
                    continue

                # 止损（基于毛利润百分比，不扣除手续费更严格）
                if gross_profit_pct <= self.stop_loss:
                    self._log("系统", f"{self.symbol} 触发止损 {gross_profit_pct*100:.2f}%，卖出")
                    self._sell_all(raw_qty, price)
                    break

                # 保底卖出
                hold_time = now - self.entry_time
                if hold_time > self.max_hold_hours * 3600 and profit_pct > 0:
                    self._log("系统", f"{self.symbol} 持仓超过{self.max_hold_hours}小时且盈利，保底卖出")
                    self._sell_all(raw_qty, price)
                    break

                # 盈利保护
                if self.highest_price_since_entry > 0 and profit_pct > 0:
                    drawdown = (self.highest_price_since_entry - price) / self.highest_price_since_entry
                    if drawdown >= 0.005:
                        self._log("系统", f"{self.symbol} 触发盈利保护（从最高点回撤{drawdown*100:.1f}%），卖出")
                        self._sell_all(raw_qty, price)
                        break

                # 移动止盈
                if profit_pct > 0 and self.highest_price_since_entry > 0:
                    drawdown = (self.highest_price_since_entry - price) / self.highest_price_since_entry
                    if drawdown >= self.trailing_stop:
                        self._log("系统", f"{self.symbol} 触发移动止盈（从最高点回撤{drawdown*100:.1f}%），卖出")
                        self._sell_all(raw_qty, price)
                        break

                # 分级止盈
                if profit_pct > 0:
                    total_sold = 0
                    remaining_qty = current_qty
                    for level, ratio in zip(self.take_profit_levels, self.sell_ratios):
                        if profit_pct >= level:
                            sell_qty = math.floor(remaining_qty * ratio / self.step) * self.step
                            if sell_qty > 0:
                                if sell_qty * price < self.min_order_value:
                                    self._log("系统", f"{self.symbol} 分级止盈跳过：卖出数量 {sell_qty} 价值 {sell_qty*price:.2f} USDT 小于最小订单额 {self.min_order_value}")
                                    continue
                                self._sell_partial(sell_qty, price)
                                total_sold += sell_qty
                                # 更新剩余持仓
                                self.sync_position_from_balance()
                                remaining_qty = self.position["qty"]
                            else:
                                break
                    if total_sold > 0 and self.position["qty"] == 0:
                        break

                time.sleep(5)

            except Exception as e:
                self._log("系统", f"{self.symbol} 卖出线程异常: {e}")
                time.sleep(5)

        self._cleanup()

    def _sell_all(self, qty, price):
        try:
            # 重新获取最新持仓
            self.sync_position_from_balance()
            if self.position["qty"] <= 0:
                return
            sell_qty = min(qty, self.position["qty"])
            raw_qty = math.floor(sell_qty / self.step) * self.step
            if raw_qty <= 0:
                return
            if raw_qty * price < self.min_order_value:
                self._log("系统", f"{self.symbol} 卖出总价值 {raw_qty*price:.2f} USDT 小于最小订单额 {self.min_order_value}，跳过卖出")
                return

            order_id = self.market_sell(raw_qty)
            sell_value = raw_qty * price
            sell_fee = sell_value * self.config.get("slippage", 0.001)
            avg_price = self.position["avg_price"] if self.position["avg_price"] else 0
            # 买入时也支付了手续费，需要扣除（假设买入时已经支付，卖出时不再重复扣除买入手续费）
            # 为简化，这里只扣除卖出手续费，盈亏计算会略高估盈利，但可接受
            pnl = sell_value - (avg_price * raw_qty) - sell_fee

            self.position["has_position"] = False
            self.position["qty"] = 0.0
            self._clear_position_in_db()

            record_trade(
                user_id=self.user_id,
                key_id=self.key_id,
                bot_mode="global",
                sub_mode="sell",
                symbol=self.symbol,
                side="sell",
                price=price,
                quantity=raw_qty,
                amount_usdt=sell_value,
                fee=sell_fee,
                order_id=order_id,
                pnl=pnl,
                exit_reason="stop_loss" if pnl < 0 else "take_profit",
                hold_seconds=int(time.time() - self.entry_time),
                market_state="unknown"
            )
            if self.callback:
                self.callback(self.key_id, self.symbol, "卖出", price, time.time())
            self._log("系统", f"{self.symbol} 卖出 {raw_qty:.6f}, 净盈亏: {pnl:.2f} USDT", price)
        except Exception as e:
            if self.callback:
                self.callback(self.key_id, self.symbol, "系统", price, time.time(), msg=f"卖出失败: {e}")

    def _sell_partial(self, qty, price):
        try:
            # 重新获取最新持仓
            self.sync_position_from_balance()
            if self.position["qty"] <= 0:
                return
            sell_qty = min(qty, self.position["qty"])
            raw_qty = math.floor(sell_qty / self.step) * self.step
            if raw_qty <= 0:
                return
            if raw_qty * price < self.min_order_value:
                self._log("系统", f"{self.symbol} 部分卖出价值 {raw_qty*price:.2f} USDT 小于最小订单额 {self.min_order_value}，跳过卖出")
                return

            order_id = self.market_sell(raw_qty)
            sold_value = raw_qty * price
            sell_fee = sold_value * self.config.get("slippage", 0.001)
            avg_price = self.position["avg_price"] if self.position["avg_price"] else 0
            pnl = sold_value - (avg_price * raw_qty) - sell_fee

            self.position["qty"] -= raw_qty
            if self.position["qty"] > 0:
                self._save_position_to_db()
            else:
                self._clear_position_in_db()

            record_trade(
                user_id=self.user_id,
                key_id=self.key_id,
                bot_mode="global",
                sub_mode="sell",
                symbol=self.symbol,
                side="sell",
                price=price,
                quantity=raw_qty,
                amount_usdt=sold_value,
                fee=sell_fee,
                order_id=order_id,
                pnl=pnl,
                exit_reason="take_profit_partial",
                hold_seconds=int(time.time() - self.entry_time),
                market_state="unknown"
            )
            if self.callback:
                self.callback(self.key_id, self.symbol, "卖出", price, time.time())
            self._log("系统", f"{self.symbol} 部分卖出 {raw_qty:.6f}, 净盈亏: {pnl:.2f} USDT", price)
        except Exception as e:
            if self.callback:
                self.callback(self.key_id, self.symbol, "系统", price, time.time(), msg=f"卖出失败: {e}")

    def _cleanup(self):
        if self.key_service:
            self.key_service.stop_bot(self.key_id, self.symbol)
            key = self.key_service.get_key(self.key_id)
            if key:
                if self.symbol in key['symbols']:
                    from dao.symbol_config_dao import SymbolConfigDAO
                    db_id = key['symbols'][self.symbol].get('db_id')
                    if db_id:
                        SymbolConfigDAO.delete(db_id)
                    del key['symbols'][self.symbol]
                if self.symbol in key['bots']:
                    del key['bots'][self.symbol]
            if self.callback:
                self.callback(self.key_id, self.symbol, "系统", 0, time.time(), msg=f"{self.symbol} 已卖出并清理")
                self.callback(self.key_id, self.symbol, "更新UI", 0, time.time())