# 文件路径: gui/global_buy_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox

class GlobalBuyDialog:
    def __init__(self, parent, callback):
        self.parent = parent
        self.callback = callback
        self.root = tk.Toplevel(parent)
        self.root.title("全局买入配置")
        self.root.geometry("400x200")
        self.root.transient(parent)
        self.root.grab_set()

        self.root.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.root.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.root.winfo_height()) // 2
        self.root.geometry(f"+{x}+{y}")

        self.create_widgets()

    def create_widgets(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="最大买入金额(USDT):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.max_buy_entry = ttk.Entry(frame, width=15)
        self.max_buy_entry.grid(row=0, column=1, sticky=tk.W, pady=5)
        self.max_buy_entry.insert(0, "15")

        ttk.Label(frame, text="最大补仓金额(USDT):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.max_add_entry = ttk.Entry(frame, width=15)
        self.max_add_entry.grid(row=1, column=1, sticky=tk.W, pady=5)
        self.max_add_entry.insert(0, "10")

        ttk.Label(frame, text="买入评分阈值:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.score_threshold_entry = ttk.Entry(frame, width=15)
        self.score_threshold_entry.grid(row=2, column=1, sticky=tk.W, pady=5)
        self.score_threshold_entry.insert(0, "6")

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="启动", command=self.on_start).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.root.destroy).pack(side=tk.LEFT, padx=5)

    def on_start(self):
        try:
            max_buy = float(self.max_buy_entry.get().strip()) if self.max_buy_entry.get().strip() else None
            max_add = float(self.max_add_entry.get().strip()) if self.max_add_entry.get().strip() else None
            score_threshold = int(self.score_threshold_entry.get().strip()) if self.score_threshold_entry.get().strip() else 4
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")
            return

        config = {
            "max_buy_amount": max_buy,
            "max_add_amount": max_add,
            "global_buy_score_threshold": score_threshold,
            "global_take_profit": 0.05,
            "global_stop_loss": -0.03,
            "global_trailing_stop": 0.02,
            "global_max_hold_hours": 24,
            "global_buy_ratio": 0.5,
            "global_add_buy_ratio": 0.3,
            "global_add_buy_drop": 0.03,
        }
        self.callback(config)
        self.root.destroy()