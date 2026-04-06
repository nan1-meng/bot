# 文件路径: gui/widgets/risk_panel.py
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, Callable

class RiskPanel(ttk.LabelFrame):
    """风控配置面板"""

    def __init__(self, parent, on_change: Callable = None):
        super().__init__(parent, text="风控设置", padding=5)
        self.on_change = on_change
        self.create_widgets()

    def create_widgets(self):
        row = 0
        # 每日亏损限制
        ttk.Label(self, text="每日最大亏损 (USDT):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.daily_loss_var = tk.StringVar(value="100")
        entry = ttk.Entry(self, width=10, textvariable=self.daily_loss_var)
        entry.grid(row=row, column=1, sticky=tk.W, pady=2)
        entry.bind('<FocusOut>', lambda e: self._notify())
        row += 1

        ttk.Label(self, text="每日最大交易次数:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.daily_trades_var = tk.StringVar(value="50")
        entry = ttk.Entry(self, width=10, textvariable=self.daily_trades_var)
        entry.grid(row=row, column=1, sticky=tk.W, pady=2)
        entry.bind('<FocusOut>', lambda e: self._notify())
        row += 1

        ttk.Label(self, text="最大回撤比例 (%):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.max_dd_var = tk.StringVar(value="10")
        entry = ttk.Entry(self, width=10, textvariable=self.max_dd_var)
        entry.grid(row=row, column=1, sticky=tk.W, pady=2)
        entry.bind('<FocusOut>', lambda e: self._notify())
        row += 1

        ttk.Label(self, text="熔断时间 (秒):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.breaker_var = tk.StringVar(value="300")
        entry = ttk.Entry(self, width=10, textvariable=self.breaker_var)
        entry.grid(row=row, column=1, sticky=tk.W, pady=2)
        entry.bind('<FocusOut>', lambda e: self._notify())
        row += 1

        ttk.Label(self, text="初始资金 (USDT):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.init_balance_var = tk.StringVar(value="1000")
        entry = ttk.Entry(self, width=10, textvariable=self.init_balance_var)
        entry.grid(row=row, column=1, sticky=tk.W, pady=2)
        entry.bind('<FocusOut>', lambda e: self._notify())
        row += 1

        ttk.Label(self, text="每笔风险比例 (%):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.risk_per_trade_var = tk.StringVar(value="2")
        entry = ttk.Entry(self, width=10, textvariable=self.risk_per_trade_var)
        entry.grid(row=row, column=1, sticky=tk.W, pady=2)
        entry.bind('<FocusOut>', lambda e: self._notify())
        row += 1

        ttk.Label(self, text="最大持仓占比 (%):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.max_pos_ratio_var = tk.StringVar(value="50")
        entry = ttk.Entry(self, width=10, textvariable=self.max_pos_ratio_var)
        entry.grid(row=row, column=1, sticky=tk.W, pady=2)
        entry.bind('<FocusOut>', lambda e: self._notify())

    def _notify(self):
        if self.on_change:
            self.on_change()

    def get_config(self) -> Dict[str, Any]:
        try:
            return {
                "daily_loss_limit": float(self.daily_loss_var.get()),
                "daily_trade_limit": int(self.daily_trades_var.get()),
                "max_drawdown": float(self.max_dd_var.get()) / 100.0,
                "circuit_breaker_time": int(self.breaker_var.get()),
                "initial_balance": float(self.init_balance_var.get()),
                "risk_per_trade": float(self.risk_per_trade_var.get()) / 100.0,
                "max_position_ratio": float(self.max_pos_ratio_var.get()) / 100.0
            }
        except ValueError:
            return {}

    def set_config(self, config: Dict[str, Any]):
        self.daily_loss_var.set(str(config.get("daily_loss_limit", 100)))
        self.daily_trades_var.set(str(config.get("daily_trade_limit", 50)))
        self.max_dd_var.set(str(config.get("max_drawdown", 0.1) * 100))
        self.breaker_var.set(str(config.get("circuit_breaker_time", 300)))
        self.init_balance_var.set(str(config.get("initial_balance", 1000)))
        self.risk_per_trade_var.set(str(config.get("risk_per_trade", 0.02) * 100))
        self.max_pos_ratio_var.set(str(config.get("max_position_ratio", 0.5) * 100))