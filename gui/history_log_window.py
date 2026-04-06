# 文件路径: gui/history_log_window.py
import tkinter as tk
from tkinter import ttk
from dao.system_log_dao import SystemLogDAO

class HistoryLogWindow:
    def __init__(self, user_id, key_service, log_callback):
        self.user_id = user_id
        self.key_service = key_service
        self.log_callback = log_callback
        self.root = tk.Toplevel()
        self.root.title("历史日志")
        self.root.geometry("900x600")
        self.create_widgets()
        self.load_logs()
        self.root.mainloop()

    def create_widgets(self):
        filter_frame = ttk.LabelFrame(self.root, text="筛选", padding=5)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text="Key:").grid(row=0, column=0, padx=5, sticky=tk.W)
        self.key_var = tk.StringVar(value="全部")
        self.key_combo = ttk.Combobox(filter_frame, textvariable=self.key_var, width=20, state="readonly")
        self.key_combo.grid(row=0, column=1, padx=5)

        ttk.Label(filter_frame, text="级别:").grid(row=0, column=2, padx=5, sticky=tk.W)
        self.level_var = tk.StringVar(value="全部")
        level_combo = ttk.Combobox(filter_frame, textvariable=self.level_var,
                                   values=["全部", "INFO", "WARNING", "ERROR"], width=10, state="readonly")
        level_combo.grid(row=0, column=3, padx=5)

        ttk.Button(filter_frame, text="查询", command=self.load_logs).grid(row=0, column=4, padx=10)

        # 日志表格
        columns = ("时间", "Key", "级别", "类别", "消息")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings", height=20)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150)
        self.tree.column("时间", width=150)
        self.tree.column("消息", width=400)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 加载 Key 列表
        keys = self.key_service.get_all_keys()
        key_options = ["全部"]
        for key_id in keys:
            key = self.key_service.get_key(key_id)
            if key:
                key_options.append(f"{key_id}: {key.get('platform', 'bybit').upper()}")
        self.key_combo['values'] = key_options
        if key_options:
            self.key_combo.current(0)

    def load_logs(self):
        key_sel = self.key_var.get()
        key_id = None
        if key_sel != "全部":
            try:
                key_id = int(key_sel.split(":")[0])
            except:
                pass
        level_sel = self.level_var.get()
        level = None if level_sel == "全部" else level_sel

        logs = SystemLogDAO.get_logs(self.user_id, key_id, level, limit=1000)
        for row in self.tree.get_children():
            self.tree.delete(row)
        for log in logs:
            key_display = f"{log.key_id}" if log.key_id else "-"
            self.tree.insert("", tk.END, values=(
                log.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                key_display,
                log.level,
                log.category or "-",
                log.message[:200]
            ))