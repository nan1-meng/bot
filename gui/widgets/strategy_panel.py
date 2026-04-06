# 文件路径: gui/widgets/strategy_panel.py
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Callable

class StrategyPanel(ttk.LabelFrame):
    """策略配置面板，允许用户启用/禁用策略、调整权重和参数"""

    def __init__(self, parent, on_change: Callable = None):
        super().__init__(parent, text="策略配置", padding=5)
        self.on_change = on_change
        self.strategies = {}
        self.create_widgets()

    def create_widgets(self):
        self.available = [
            ("RSI", {"period": 14, "oversold": 30, "overbought": 70}),
            ("Bollinger", {"period": 20, "num_std": 2}),
            ("MACD", {"fast": 12, "slow": 26, "signal": 9}),
            ("SMA", {"short": 20, "long": 50}),
            ("Volume", {"period": 20, "ratio": 1.2})
        ]

        # 添加组合模式选择
        mode_frame = ttk.Frame(self)
        mode_frame.pack(fill=tk.X, pady=5)
        ttk.Label(mode_frame, text="信号合并模式:").pack(side=tk.LEFT, padx=5)
        self.combine_mode_var = tk.StringVar(value="weighted")
        mode_combo = ttk.Combobox(mode_frame, textvariable=self.combine_mode_var,
                                  values=["weighted", "max", "min", "vote"], state="readonly", width=10)
        mode_combo.pack(side=tk.LEFT)
        mode_combo.bind("<<ComboboxSelected>>", lambda e: self._notify())

        for name, params in self.available:
            frame = ttk.Frame(self)
            frame.pack(fill=tk.X, pady=2)

            enabled = tk.BooleanVar(value=True)
            cb = ttk.Checkbutton(frame, text=name, variable=enabled, command=self._notify)
            cb.pack(side=tk.LEFT)

            ttk.Label(frame, text="权重:").pack(side=tk.LEFT, padx=(10,2))
            weight_var = tk.StringVar(value="1.0")
            entry = ttk.Entry(frame, width=5, textvariable=weight_var)
            entry.pack(side=tk.LEFT)
            entry.bind('<FocusOut>', lambda e, n=name: self._on_weight_change(n))

            ttk.Button(frame, text="参数", command=lambda n=name: self._edit_params(n)).pack(side=tk.LEFT, padx=5)

            self.strategies[name] = {
                "enabled": enabled,
                "weight": weight_var,
                "params": params.copy()
            }

    def _on_weight_change(self, name):
        try:
            w = float(self.strategies[name]["weight"].get())
            if w < 0:
                self.strategies[name]["weight"].set("0")
        except ValueError:
            self.strategies[name]["weight"].set("1.0")
        self._notify()

    def _edit_params(self, name):
        dialog = tk.Toplevel(self)
        dialog.title(f"{name} 策略参数")
        dialog.transient(self)
        dialog.grab_set()
        entries = {}
        params = self.strategies[name]["params"]
        for i, (k, v) in enumerate(params.items()):
            ttk.Label(dialog, text=k).grid(row=i, column=0, padx=5, pady=2, sticky=tk.W)
            var = tk.StringVar(value=str(v))
            entry = ttk.Entry(dialog, width=10, textvariable=var)
            entry.grid(row=i, column=1, padx=5, pady=2)
            entries[k] = var

        def save():
            try:
                for k, var in entries.items():
                    val = var.get()
                    if '.' in val:
                        params[k] = float(val)
                    else:
                        params[k] = int(val)
                self.strategies[name]["params"] = params
                self._notify()
                dialog.destroy()
            except ValueError:
                messagebox.showerror("错误", "参数必须是数字")

        ttk.Button(dialog, text="确定", command=save).grid(row=len(params), column=0, pady=10)
        ttk.Button(dialog, text="取消", command=dialog.destroy).grid(row=len(params), column=1, pady=10)

    def _notify(self):
        if self.on_change:
            self.on_change()

    def get_config(self) -> Dict[str, Any]:
        strategies = []
        for name, data in self.strategies.items():
            if data["enabled"].get():
                strategies.append({
                    "name": name,
                    "enabled": True,
                    "weight": float(data["weight"].get()),
                    "params": data["params"].copy()
                })
        return {"strategies": strategies, "combine_mode": self.combine_mode_var.get()}

    def set_config(self, config: Dict[str, Any]):
        if "combine_mode" in config:
            self.combine_mode_var.set(config["combine_mode"])
        for strat in config.get("strategies", []):
            name = strat["name"]
            if name in self.strategies:
                self.strategies[name]["enabled"].set(strat.get("enabled", True))
                self.strategies[name]["weight"].set(str(strat.get("weight", 1.0)))
                self.strategies[name]["params"].update(strat.get("params", {}))