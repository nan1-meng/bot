# 文件路径: gui/assets_panel.py
import tkinter as tk
from tkinter import ttk

class AssetsPanel(ttk.Frame):
    """独立资产显示面板，可嵌入到主窗口中"""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.create_widgets()

    def create_widgets(self):
        # 使用 LabelFrame 包裹，带标题
        frame = ttk.LabelFrame(self, text="持仓资产（实时盈亏）", padding=5)
        frame.pack(fill=tk.BOTH, expand=True)

        columns = ("symbol", "数量", "现价", "市值(USDT)", "成本价", "盈亏(USDT)", "盈亏(%)")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, anchor=tk.CENTER)
        self.tree.column("symbol", width=80)
        self.tree.pack(fill=tk.BOTH, expand=True)

        # 滚动条
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def update_assets(self, assets):
        """根据 assets 字典更新表格"""
        for row in self.tree.get_children():
            self.tree.delete(row)
        for symbol, info in assets.items():
            self.tree.insert("", tk.END, values=(
                symbol,
                f"{info['qty']:.4f}",
                f"{info['price']:.6f}",
                f"{info['value']:.2f}",
                f"{info['cost']:.6f}",
                f"{info['pnl_usdt']:+.2f}",
                f"{info['pnl_pct']:+.2f}%"
            ))