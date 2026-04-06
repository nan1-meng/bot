# 文件路径: gui/chase_buy_window.py
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from dao.api_key_dao import ApiKeyDAO
from services.chase_buy_service import ChaseBuyService
from pybit.unified_trading import HTTP
from config import TESTNET
from utils.encryption import decrypt

class ChaseBuyWindow:
    def __init__(self, user_id):
        self.user_id = user_id
        self.service = None
        self.running = False
        self.selected_key_id = None
        self.selected_key_data = None
        self.balance_var = tk.StringVar(value="余额: 未选择Key")
        self.root = tk.Toplevel()
        self.root.title("追买监控")
        self.root.geometry("800x600")
        self.create_widgets()
        self.load_keys()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def create_widgets(self):
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(top_frame, text="选择Key:").pack(side=tk.LEFT, padx=5)
        self.key_combo = ttk.Combobox(top_frame, width=30, state="readonly")
        self.key_combo.pack(side=tk.LEFT, padx=5)
        self.key_combo.bind('<<ComboboxSelected>>', self.on_key_select)

        self.balance_label = tk.Label(top_frame, textvariable=self.balance_var, fg="blue")
        self.balance_label.pack(side=tk.LEFT, padx=10)

        toolbar = tk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        self.start_btn = tk.Button(toolbar, text="启动追买", command=self.start_service, state=tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=2)
        self.stop_btn = tk.Button(toolbar, text="停止追买", command=self.stop_service, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="刷新余额", command=self.refresh_balance).pack(side=tk.LEFT, padx=2)

        columns = ("币种", "状态", "持仓", "均价", "更新时间")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings", height=15)
        self.tree.heading("币种", text="币种")
        self.tree.heading("状态", text="状态")
        self.tree.heading("持仓", text="持仓")
        self.tree.heading("均价", text="均价")
        self.tree.heading("更新时间", text="更新时间")
        self.tree.column("币种", width=120)
        self.tree.column("状态", width=100)
        self.tree.column("持仓", width=120)
        self.tree.column("均价", width=120)
        self.tree.column("更新时间", width=150)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        log_frame = tk.LabelFrame(self.root, text="日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_text = tk.scrolledtext.ScrolledText(log_frame, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def load_keys(self):
        keys = ApiKeyDAO.get_by_user(self.user_id)
        self.key_list = []
        display_list = []
        for k in keys:
            if k.is_valid:
                self.key_list.append((k.id, k.key_name, k.api_key, k.api_secret))
                display_list.append(f"{k.key_name} ({k.platform})")
        self.key_combo['values'] = display_list
        if display_list:
            self.key_combo.current(0)
            self.on_key_select(None)

    def on_key_select(self, event):
        idx = self.key_combo.current()
        if idx >= 0:
            self.selected_key_id, self.selected_key_name, enc_api, enc_secret = self.key_list[idx]
            self.selected_key_data = (enc_api, enc_secret)
            self.start_btn.config(state=tk.NORMAL)
            self.refresh_balance()
        else:
            self.selected_key_id = None
            self.start_btn.config(state=tk.DISABLED)
            self.balance_var.set("余额: 未选择Key")

    def refresh_balance(self):
        if not self.selected_key_data:
            return
        enc_api, enc_secret = self.selected_key_data
        try:
            api_key_plain = decrypt(enc_api)
            secret_plain = decrypt(enc_secret)
        except Exception as e:
            self.log(f"解密失败: {e}")
            self.balance_var.set("余额: 解密失败")
            return

        try:
            session = HTTP(testnet=TESTNET, api_key=api_key_plain, api_secret=secret_plain, timeout=5)
            resp = session.get_wallet_balance(accountType="UNIFIED")
            usdt = 0.0
            for coin in resp["result"]["list"][0]["coin"]:
                if coin["coin"] == "USDT":
                    available = coin.get("availableToWithdraw", "")
                    if available == "":
                        available = coin.get("walletBalance", "0")
                    usdt = float(available) if available else 0.0
                    break
            self.balance_var.set(f"余额: {usdt:.2f} USDT")
        except Exception as e:
            self.log(f"获取余额失败: {e}")
            self.balance_var.set("余额: 获取失败")

    def log(self, msg):
        self.log_text.insert(tk.END, f"{msg}\n")
        self.log_text.see(tk.END)

    def start_service(self):
        if not self.selected_key_id:
            messagebox.showwarning("警告", "请先选择一个Key")
            return
        if self.service and self.service.is_alive():
            messagebox.showinfo("提示", "追买服务已在运行")
            return
        self.service = ChaseBuyService(self.user_id, self.selected_key_id, callback=self.log)
        self.service.start()
        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.log("追买服务已启动")

    def stop_service(self):
        if self.service:
            self.service.stop()
            self.service.join(timeout=2)
            self.service = None
        self.running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.log("追买服务已停止")

    def on_close(self):
        self.stop_service()
        self.root.destroy()