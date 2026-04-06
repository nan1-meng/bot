# 文件路径: gui/widgets/config_panel.py
import tkinter as tk
from tkinter import ttk, messagebox
import math
import threading
from utils.widgets import ToolTip

class ConfigPanel(ttk.Frame):
    def __init__(self, parent, on_start_callback):
        super().__init__(parent)
        self.on_start_callback = on_start_callback

        self.mode_var = tk.IntVar(value=0)
        self.expert_max_buy = tk.StringVar(value="")
        self.expert_max_add = tk.StringVar(value="")
        self.scalping_per_trade = tk.StringVar(value="10")
        self.scalping_target = tk.StringVar(value="1000")
        self.scalping_reward_coin = tk.StringVar(value="0")
        self.scalping_sell_interval = tk.StringVar(value="")
        self.scalping_sell_on_profit = tk.BooleanVar(value=False)
        self.scalping_min_profit_pct = tk.StringVar(value="0.2")
        self.scalping_max_hold_seconds = tk.StringVar(value="60")
        self.global_max_buy = tk.StringVar(value="")
        self.global_max_add = tk.StringVar(value="")
        self.global_max_positions = tk.StringVar(value="3")  # 新增

        self._current_key_id = None
        self._current_symbol = None
        self._key_service = None

        self.create_widgets()
        self.toggle_mode()

    def create_widgets(self):
        # 模式选择
        self.mode_frame = ttk.LabelFrame(self, text="选择模式", padding=5)
        self.mode_frame.pack(fill=tk.X, pady=5)
        ttk.Radiobutton(self.mode_frame, text="策略模式", variable=self.mode_var, value=0,
                        command=self.toggle_mode).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(self.mode_frame, text="资深模式 (AI)", variable=self.mode_var, value=1,
                        command=self.toggle_mode).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(self.mode_frame, text="刷单模式", variable=self.mode_var, value=2,
                        command=self.toggle_mode).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(self.mode_frame, text="全局模式", variable=self.mode_var, value=3,
                        command=self.toggle_mode).pack(side=tk.LEFT, padx=10)

        # ========== 策略参数框架 ==========
        self.strategy_frame = ttk.LabelFrame(self, text="策略参数", padding=5)
        self.entries = {}
        params = [
            ("rsi_period", "RSI 周期 (分钟):", "14"),
            ("rsi_oversold", "RSI 超卖阈值:", "30"),
            ("rsi_overbought", "RSI 超买阈值:", "70"),
            ("sma_short", "SMA 短期 (分钟):", "50"),
            ("sma_long", "SMA 长期 (分钟):", "200"),
            ("min_order", "最小订单价值 (USDT):", "5"),
            ("slippage", "滑点 (%):", "1"),
            ("buy_ratio", "首次买入比例 (0-1):", "0.5"),
            ("add_buy_ratio", "补仓比例 (0-1):", "0.3"),
            ("add_buy_drop", "补仓跌幅 (%):", "2"),
            ("max_buy", "单笔最大买入金额 (USDT):", ""),
            ("take_profit", "止盈目标 (%):", "0.5"),
            ("stop_loss", "止损阈值 (%):", "-2"),
        ]
        for key, label, default in params:
            row_frame = ttk.Frame(self.strategy_frame)
            row_frame.pack(fill=tk.X, pady=2)
            ttk.Label(row_frame, text=label, width=20).pack(side=tk.LEFT)
            entry = ttk.Entry(row_frame, width=10)
            entry.insert(0, default)
            entry.pack(side=tk.LEFT, padx=5)
            self.entries[key] = entry

        self.use_trend_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.strategy_frame, text="启用趋势过滤", variable=self.use_trend_var).pack(anchor=tk.W, pady=2)
        self.use_rsi_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.strategy_frame, text="启用RSI阈值", variable=self.use_rsi_var).pack(anchor=tk.W, pady=2)

        self.start_strategy_btn = ttk.Button(self.strategy_frame, text="启动策略模式到选中币种", command=self.start_strategy)
        self.start_strategy_btn.pack(pady=5)

        # ========== 资深模式（AI）框架 ==========
        self.expert_frame = ttk.LabelFrame(self, text="资深模式参数 (AI全自动决策)", padding=5)
        amount_frame = ttk.Frame(self.expert_frame)
        amount_frame.pack(anchor=tk.W, pady=5, fill=tk.X)
        ttk.Label(amount_frame, text="最大买入金额(USDT):").pack(side=tk.LEFT, padx=2)
        ttk.Entry(amount_frame, width=8, textvariable=self.expert_max_buy).pack(side=tk.LEFT, padx=2)
        ttk.Label(amount_frame, text=" (留空则不限制)").pack(side=tk.LEFT, padx=2)

        amount_frame2 = ttk.Frame(self.expert_frame)
        amount_frame2.pack(anchor=tk.W, pady=5, fill=tk.X)
        ttk.Label(amount_frame2, text="最大补仓金额(USDT):").pack(side=tk.LEFT, padx=2)
        ttk.Entry(amount_frame2, width=8, textvariable=self.expert_max_add).pack(side=tk.LEFT, padx=2)
        ttk.Label(amount_frame2, text=" (留空则不限制)").pack(side=tk.LEFT, padx=2)

        self.start_expert_btn = ttk.Button(self.expert_frame, text="启动AI模式到选中币种", command=self.start_expert)
        self.start_expert_btn.pack(pady=10)

        # ========== 刷单模式框架 ==========
        self.scalping_frame = ttk.LabelFrame(self, text="刷单模式参数", padding=5)

        param_frame = ttk.Frame(self.scalping_frame)
        param_frame.pack(fill=tk.X, pady=2)
        ttk.Label(param_frame, text="每笔买入金额(USDT):").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(param_frame, width=10, textvariable=self.scalping_per_trade).grid(row=0, column=1, sticky=tk.W, pady=2)
        ttk.Label(param_frame, text="目标交易额(USDT):").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(param_frame, width=10, textvariable=self.scalping_target).grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Label(param_frame, text="奖励币数量:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(param_frame, width=10, textvariable=self.scalping_reward_coin).grid(row=2, column=1, sticky=tk.W, pady=2)
        ttk.Label(param_frame, text="卖出间隔(秒):").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(param_frame, width=10, textvariable=self.scalping_sell_interval).grid(row=3, column=1, sticky=tk.W, pady=2)

        self.sell_on_profit_cb = ttk.Checkbutton(self.scalping_frame, text="盈利卖出模式（买入后等待盈利再卖出）",
                                                 variable=self.scalping_sell_on_profit)
        self.sell_on_profit_cb.pack(anchor=tk.W, pady=2)

        profit_frame = ttk.Frame(self.scalping_frame)
        profit_frame.pack(fill=tk.X, pady=2)
        ttk.Label(profit_frame, text="最小盈利百分比 (%):").pack(side=tk.LEFT, padx=5)
        ttk.Entry(profit_frame, width=8, textvariable=self.scalping_min_profit_pct).pack(side=tk.LEFT)
        ttk.Label(profit_frame, text=" (盈利模式)").pack(side=tk.LEFT, padx=2)

        time_frame = ttk.Frame(self.scalping_frame)
        time_frame.pack(fill=tk.X, pady=2)
        ttk.Label(time_frame, text="最大持仓时间(秒):").pack(side=tk.LEFT, padx=5)
        ttk.Entry(time_frame, width=8, textvariable=self.scalping_max_hold_seconds).pack(side=tk.LEFT)
        ttk.Label(time_frame, text=" (盈利模式)").pack(side=tk.LEFT, padx=2)

        self.start_scalping_btn = ttk.Button(self.scalping_frame, text="启动刷单模式", command=self.start_scalping)
        self.start_scalping_btn.pack(pady=5)

        self.estimate_label = ttk.Label(self.scalping_frame, text="", font=("微软雅黑", 9), foreground="blue")
        self.estimate_label.pack(anchor=tk.W, pady=2)

        self.scalping_per_trade.trace_add('write', lambda *_: self.refresh_estimate())
        self.scalping_target.trace_add('write', lambda *_: self.refresh_estimate())
        self.scalping_reward_coin.trace_add('write', lambda *_: self.refresh_estimate())
        self.scalping_sell_interval.trace_add('write', lambda *_: self.refresh_estimate())

        # ========== 全局模式框架 ==========
        self.global_frame = ttk.LabelFrame(self, text="全局模式参数 (自动扫描买入并创建卖出机器人)", padding=5)
        global_param_frame = ttk.Frame(self.global_frame)
        global_param_frame.pack(fill=tk.X, pady=5)

        ttk.Label(global_param_frame, text="最大买入金额(USDT):").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(global_param_frame, width=10, textvariable=self.global_max_buy).grid(row=0, column=1, sticky=tk.W, pady=2)
        ttk.Label(global_param_frame, text=" (留空则自动)").grid(row=0, column=2, sticky=tk.W, pady=2)

        ttk.Label(global_param_frame, text="最大补仓金额(USDT):").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(global_param_frame, width=10, textvariable=self.global_max_add).grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Label(global_param_frame, text=" (留空则自动)").grid(row=1, column=2, sticky=tk.W, pady=2)

        ttk.Label(global_param_frame, text="最大同时持仓数:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(global_param_frame, width=10, textvariable=self.global_max_positions).grid(row=2, column=1, sticky=tk.W, pady=2)
        ttk.Label(global_param_frame, text=" (默认3)").grid(row=2, column=2, sticky=tk.W, pady=2)

        self.start_global_btn = ttk.Button(self.global_frame, text="启动全局模式", command=self.start_global)
        self.start_global_btn.pack(pady=10)
        self.stop_global_btn = ttk.Button(self.global_frame, text="停止全局模式", command=self.stop_global, state=tk.DISABLED)
        self.stop_global_btn.pack(pady=5)

        # 初始隐藏所有子框架
        self.strategy_frame.pack_forget()
        self.expert_frame.pack_forget()
        self.scalping_frame.pack_forget()
        self.global_frame.pack_forget()

    def toggle_mode(self):
        self.strategy_frame.pack_forget()
        self.expert_frame.pack_forget()
        self.scalping_frame.pack_forget()
        self.global_frame.pack_forget()
        mode = self.mode_var.get()
        if mode == 0:
            self.strategy_frame.pack(fill=tk.X, pady=5, after=self.mode_frame)
        elif mode == 1:
            self.expert_frame.pack(fill=tk.X, pady=5, after=self.mode_frame)
        elif mode == 2:
            self.scalping_frame.pack(fill=tk.X, pady=5, after=self.mode_frame)
        else:
            self.global_frame.pack(fill=tk.X, pady=5, after=self.mode_frame)

    def get_strategy_config(self):
        def get_float(key, default):
            val = self.entries[key].get().strip()
            return float(val) if val else default
        def get_int(key, default):
            val = self.entries[key].get().strip()
            return int(float(val)) if val else default

        max_buy_val = self.entries["max_buy"].get().strip()
        max_buy = float(max_buy_val) if max_buy_val else None

        return {
            "rsi_period": get_int("rsi_period", 14),
            "rsi_oversold": get_float("rsi_oversold", 30),
            "rsi_overbought": get_float("rsi_overbought", 70),
            "sma_short": get_int("sma_short", 50),
            "sma_long": get_int("sma_long", 200),
            "min_order_value": get_float("min_order", 5),
            "slippage": get_float("slippage", 1) / 100.0,
            "buy_ratio": get_float("buy_ratio", 0.5),
            "add_buy_ratio": get_float("add_buy_ratio", 0.3),
            "add_buy_drop": get_float("add_buy_drop", 2) / 100.0,
            "max_buy_amount": max_buy,
            "take_profit": get_float("take_profit", 0.5) / 100.0,
            "stop_loss": get_float("stop_loss", -2) / 100.0,
            "use_trend_filter": self.use_trend_var.get(),
            "use_rsi_threshold": self.use_rsi_var.get(),
            "min_trade_interval": 60,
        }

    def get_expert_config(self):
        base_config = {
            "min_order_value": 5.0,
            "slippage": 0.001,
            "buy_ratio": 0.5,
            "add_buy_ratio": 0.3,
            "add_buy_drop": 0.02,
            "take_profit": 0.005,
            "stop_loss": -0.02,
            "fast_sell": True,
        }
        max_buy_str = self.expert_max_buy.get().strip()
        base_config["max_buy_amount"] = float(max_buy_str) if max_buy_str else None
        max_add_str = self.expert_max_add.get().strip()
        base_config["max_add_amount"] = float(max_add_str) if max_add_str else None
        return base_config, "AI模式"

    def get_scalping_config(self, current_price):
        """获取刷单配置，current_price 为 None 时返回 None"""
        if current_price is None:
            return None, 0.0, 0.0
        try:
            per_trade = float(self.scalping_per_trade.get().strip())
            target = float(self.scalping_target.get().strip())
            reward_coin = float(
                self.scalping_reward_coin.get().strip()) if self.scalping_reward_coin.get().strip() else 0.0
            sell_interval_str = self.scalping_sell_interval.get().strip()
            sell_interval = None if sell_interval_str == "" else float(sell_interval_str)
            reward_amount = reward_coin * current_price
            sell_on_profit = self.scalping_sell_on_profit.get()
            min_profit_pct = float(
                self.scalping_min_profit_pct.get().strip()) / 100.0 if self.scalping_min_profit_pct.get().strip() else 0.002
            max_hold_seconds = int(
                self.scalping_max_hold_seconds.get().strip()) if self.scalping_max_hold_seconds.get().strip() else 60
        except ValueError:
            return None, 0.0, 0.0
        return {
            "scalping_mode": True,
            "per_trade_amount": per_trade,
            "turnover_target": target,
            "reward_amount": reward_amount,
            "sell_interval": sell_interval,
            "slippage": 0.001,
            "min_order_value": 5,
            "reward_coin": reward_coin,
            "sell_on_profit": sell_on_profit,
            "min_profit_pct": min_profit_pct,
            "max_hold_seconds": max_hold_seconds,
        }, reward_coin, reward_amount

    def get_global_config(self):
        config = {
            "global_mode": True,
            "min_order_value": 5.0,
            "slippage": 0.001,
            "take_profit": 0.005,
            "stop_loss": -0.02,
            "trailing_stop": 0.01,
            "max_hold_hours": 24,
        }
        max_buy_str = self.global_max_buy.get().strip()
        config["max_buy_amount"] = float(max_buy_str) if max_buy_str else None
        max_add_str = self.global_max_add.get().strip()
        config["max_add_amount"] = float(max_add_str) if max_add_str else None
        max_pos_str = self.global_max_positions.get().strip()
        config["max_positions"] = int(max_pos_str) if max_pos_str else 3
        return config

    def start_strategy(self):
        try:
            config = self.get_strategy_config()
            self.on_start_callback("strategy", config)
        except ValueError as e:
            messagebox.showerror("参数错误", str(e))

    def start_expert(self):
        config, mode_display = self.get_expert_config()
        self.on_start_callback("expert", config, mode_display)

    def start_scalping(self):
        self.on_start_callback("scalping", None)

    def start_global(self):
        config = self.get_global_config()
        self.on_start_callback("global", config)

    def stop_global(self):
        self.on_start_callback("global_stop", None)

    def refresh_estimate(self):
        """异步刷新预估数据，避免阻塞 GUI"""
        if not hasattr(self, '_key_service') or not self._key_service:
            self.estimate_label.config(text="请先选择 Key")
            return
        if not self._current_symbol:
            self.estimate_label.config(text="请先选择币种")
            return
        if not self._current_key_id:
            self.estimate_label.config(text="请先选择 Key")
            return
        key = self._key_service.get_key(self._current_key_id)
        if not key:
            self.estimate_label.config(text="Key 不存在")
            return

        try:
            per_trade = float(self.scalping_per_trade.get().strip())
            target = float(self.scalping_target.get().strip())
            reward_coin = float(self.scalping_reward_coin.get().strip()) if self.scalping_reward_coin.get().strip() else 0.0
            sell_interval_str = self.scalping_sell_interval.get().strip()
            sell_interval = 0.2 if sell_interval_str == "" else float(sell_interval_str)
        except ValueError:
            self.estimate_label.config(text="请输入有效的数字")
            return

        # 启动后台线程获取价格
        def fetch_price():
            try:
                from clients import create_client
                client = create_client(key['platform'], key['api_key'], key['secret'], testnet=False, timeout=10)
                price = client.get_ticker(self._current_symbol)
                return price
            except Exception as e:
                return None

        def update_ui(price):
            if self._current_symbol is None:
                self.estimate_label.config(text="请先选择币种")
                return
            if price is None:
                self.estimate_label.config(text="获取价格失败，请检查网络")
                return

            slippage = 0.001
            est_buy_qty = per_trade / price
            est_sell_amount = est_buy_qty * price * (1 - slippage)
            est_loss_per_trade = per_trade - est_sell_amount
            turnover_per_round = per_trade + est_sell_amount
            est_rounds = max(1, math.ceil(target / turnover_per_round))
            est_total_buy = est_rounds * per_trade
            est_total_sell = est_rounds * est_sell_amount
            est_total_wear = est_total_buy - est_total_sell
            reward_amount = reward_coin * price
            est_net = est_total_sell - est_total_buy + reward_amount

            lines = [
                f"当前价格: {price:.6f}",
                f"每笔买入 {per_trade} USDT → {est_buy_qty:.4f} {self._current_symbol.replace('USDT','')}",
                f"每笔卖出约 {est_sell_amount:.2f} USDT (滑点 {slippage*100:.1f}%)",
                f"每笔磨损: {est_loss_per_trade:.2f} USDT",
                f"目标 {target} USDT 约需 {est_rounds} 次完整买卖",
                f"总买入: {est_total_buy:.2f}, 总卖出: {est_total_sell:.2f}",
                f"总磨损: {est_total_wear:.2f} USDT",
                f"净盈亏(含奖励): {est_net:+.2f} USDT (奖励币 {reward_coin} ≈ {reward_amount:.2f} USDT)",
                f"卖出间隔: {sell_interval} 秒"
            ]
            self.estimate_label.config(text="\n".join(lines))

        def task():
            price = fetch_price()
            self.after(0, lambda: update_ui(price))

        threading.Thread(target=task, daemon=True).start()

    def set_current_symbol(self, symbol):
        self._current_symbol = symbol

    def set_key_service(self, key_service, key_id):
        self._key_service = key_service
        self._current_key_id = key_id

    def set_config(self, config):
        if not config:
            return
        for key, entry in self.entries.items():
            entry.delete(0, tk.END)
            val = config.get(key)
            if val is None:
                entry.insert(0, "")
                continue
            if key == "slippage":
                entry.insert(0, str(val * 100))
            elif key == "add_buy_drop":
                entry.insert(0, str(val * 100))
            elif key in ["take_profit", "stop_loss"]:
                entry.insert(0, str(val * 100))
            else:
                entry.insert(0, str(val))
        max_buy = config.get("max_buy_amount")
        self.expert_max_buy.set(str(max_buy) if max_buy is not None else "")
        max_add = config.get("max_add_amount")
        self.expert_max_add.set(str(max_add) if max_add is not None else "")
        self.use_trend_var.set(config.get("use_trend_filter", True))
        self.use_rsi_var.set(config.get("use_rsi_threshold", True))
        if config.get("scalping_mode"):
            self.scalping_per_trade.set(str(config.get("per_trade_amount", "10")))
            self.scalping_target.set(str(config.get("turnover_target", "1000")))
            self.scalping_reward_coin.set(str(config.get("reward_coin", "0")))
            val = config.get("sell_interval")
            self.scalping_sell_interval.set(str(val) if val is not None else "")
            self.scalping_sell_on_profit.set(config.get("sell_on_profit", False))
            self.scalping_min_profit_pct.set(str(config.get("min_profit_pct", 0.002) * 100))
            self.scalping_max_hold_seconds.set(str(config.get("max_hold_seconds", 60)))
        if config.get("global_mode"):
            self.global_max_buy.set(str(config.get("max_buy_amount", "")))
            self.global_max_add.set(str(config.get("max_add_amount", "")))
            self.global_max_positions.set(str(config.get("max_positions", 3)))

    def clear_config(self):
        for key in self.entries:
            self.entries[key].delete(0, tk.END)
        self.entries["rsi_period"].insert(0, "14")
        self.entries["rsi_oversold"].insert(0, "30")
        self.entries["rsi_overbought"].insert(0, "70")
        self.entries["sma_short"].insert(0, "50")
        self.entries["sma_long"].insert(0, "200")
        self.entries["min_order"].insert(0, "5")
        self.entries["slippage"].insert(0, "1")
        self.entries["buy_ratio"].insert(0, "0.5")
        self.entries["add_buy_ratio"].insert(0, "0.3")
        self.entries["add_buy_drop"].insert(0, "2")
        self.entries["take_profit"].insert(0, "0.5")
        self.entries["stop_loss"].insert(0, "-2")
        self.entries["max_buy"].delete(0, tk.END)
        self.expert_max_buy.set("")
        self.expert_max_add.set("")
        self.use_trend_var.set(True)
        self.use_rsi_var.set(True)
        self.scalping_per_trade.set("10")
        self.scalping_target.set("1000")
        self.scalping_reward_coin.set("0")
        self.scalping_sell_interval.set("")
        self.scalping_sell_on_profit.set(False)
        self.scalping_min_profit_pct.set("0.2")
        self.scalping_max_hold_seconds.set("60")
        self.global_max_buy.set("")
        self.global_max_add.set("")
        self.global_max_positions.set("3")

    def update_global_buttons(self, is_running):
        """更新全局模式按钮状态"""
        if is_running:
            self.start_global_btn.config(state=tk.DISABLED)
            self.stop_global_btn.config(state=tk.NORMAL)
        else:
            self.start_global_btn.config(state=tk.NORMAL)
            self.stop_global_btn.config(state=tk.DISABLED)