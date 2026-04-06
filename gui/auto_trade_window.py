# 文件路径: gui/auto_trade_window.py
import tkinter as tk
from tkinter import ttk, messagebox
from dao.auto_trade_dao import AutoTradeDAO
from services.auto_trade_service import AutoTradeService

class AutoTradeWindow:
    def __init__(self, user_id, key_id, key_service, log_callback):
        self.user_id = user_id
        self.key_id = key_id
        self.key_service = key_service
        self.log_callback = log_callback
        self.service = None
        self.running = False

        self.root = tk.Toplevel()
        self.root.title("自动交易监控")
        self.root.geometry("800x500")
        self.create_widgets()
        self.load_tasks()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def create_widgets(self):
        toolbar = tk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        self.start_btn = tk.Button(toolbar, text="启动服务", command=self.start_service)
        self.start_btn.pack(side=tk.LEFT, padx=2)
        self.stop_btn = tk.Button(toolbar, text="停止服务", command=self.stop_service, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="刷新", command=self.load_tasks).pack(side=tk.LEFT, padx=2)

        columns = ("币种", "状态", "持仓数量", "均价", "当前价", "盈亏", "上次交易时间")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings", height=15)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        self.tree.column("币种", width=100)
        self.tree.column("持仓数量", width=120)
        self.tree.column("均价", width=100)
        self.tree.column("当前价", width=100)
        self.tree.column("盈亏", width=150)
        self.tree.column("上次交易时间", width=150)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        log_frame = tk.LabelFrame(self.root, text="日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_text = tk.scrolledtext.ScrolledText(log_frame, height=8)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def log(self, msg):
        self.log_text.insert(tk.END, f"{msg}\n")
        self.log_text.see(tk.END)
        if self.log_callback:
            self.log_callback(msg)

    def load_tasks(self):
        tasks = AutoTradeDAO.get_all_tasks(self.user_id, self.key_id)
        for row in self.tree.get_children():
            self.tree.delete(row)
        key = self.key_service.get_key(self.key_id)
        if not key:
            return
        balances = key.get('last_balances', {})
        prices = key.get('last_prices', {})

        for task in tasks:
            symbol = task.symbol
            status = task.status
            qty = float(task.position_qty)
            avg = float(task.avg_price)
            last_time = task.last_trade_time.strftime("%H:%M:%S") if task.last_trade_time else ""
            current_price = prices.get(symbol, 0)
            if current_price and avg > 0:
                pnl = (current_price - avg) * qty
                pnl_pct = (current_price - avg) / avg * 100
                pnl_str = f"{pnl:.2f} ({pnl_pct:.2f}%)"
            else:
                pnl_str = "-"
            self.tree.insert("", tk.END, values=(
                symbol, status, f"{qty:.4f}", f"{avg:.6f}",
                f"{current_price:.6f}", pnl_str, last_time
            ))

    def start_service(self):
        if self.service and self.service.is_alive():
            messagebox.showinfo("提示", "服务已在运行")
            return
        self.service = AutoTradeService(self.user_id, self.key_id, callback=self.log)
        self.service.start()
        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.log("自动交易服务已启动")

    def stop_service(self):
        if self.service:
            self.service.stop()
            self.service.join(timeout=2)
            self.service = None
        self.running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.log("自动交易服务已停止")

    def on_close(self):
        self.stop_service()
        self.root.destroy()