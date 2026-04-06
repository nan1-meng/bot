# 文件路径: gui/learning_report_window.py
import tkinter as tk
from tkinter import ttk
import json
from core.learning_reporter import LearningReporter
from dao.learning_report_dao import LearningReportDAO  # 需创建，也可直接使用 LearningReporter 的方法

class LearningReportWindow:
    def __init__(self, user_id, key_service):
        self.user_id = user_id
        self.key_service = key_service
        self.root = tk.Toplevel()
        self.root.title("学习报告 - 参数调整记录")
        self.root.geometry("900x600")

        self.create_widgets()
        self.load_reports()
        self.root.mainloop()

    def create_widgets(self):
        # 筛选框架
        filter_frame = ttk.LabelFrame(self.root, text="筛选", padding=5)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text="类型:").grid(row=0, column=0, padx=5, sticky=tk.W)
        self.type_var = tk.StringVar(value="全部")
        type_combo = ttk.Combobox(filter_frame, textvariable=self.type_var,
                                   values=["全部", "parameter_adjustment", "loss_analysis", "win_analysis"],
                                   width=20, state="readonly")
        type_combo.grid(row=0, column=1, padx=5)

        ttk.Label(filter_frame, text="币种:").grid(row=0, column=2, padx=5, sticky=tk.W)
        self.symbol_var = tk.StringVar(value="全部")
        self.symbol_combo = ttk.Combobox(filter_frame, textvariable=self.symbol_var, width=15, state="readonly")
        self.symbol_combo.grid(row=0, column=3, padx=5)

        ttk.Button(filter_frame, text="查询", command=self.load_reports).grid(row=0, column=4, padx=10)

        # 报告列表
        columns = ("时间", "类型", "币种", "内容")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings", height=20)
        self.tree.heading("时间", text="时间")
        self.tree.heading("类型", text="类型")
        self.tree.heading("币种", text="币种")
        self.tree.heading("内容", text="内容")
        self.tree.column("时间", width=150)
        self.tree.column("类型", width=120)
        self.tree.column("币种", width=80)
        self.tree.column("内容", width=500)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 加载币种列表
        self._load_symbols()

    def _load_symbols(self):
        # 获取所有已配置币种
        symbols = set()
        for key_id in self.key_service.get_all_keys():
            key = self.key_service.get_key(key_id)
            if key:
                symbols.update(key['symbols'].keys())
        symbol_list = ["全部"] + sorted(list(symbols))
        self.symbol_combo['values'] = symbol_list
        if symbol_list:
            self.symbol_combo.current(0)

    def load_reports(self):
        report_type = self.type_var.get()
        if report_type == "全部":
            report_type = None
        symbol = self.symbol_var.get()
        if symbol == "全部":
            symbol = None

        from dao.learning_report_dao import LearningReportDAO
        reports = LearningReportDAO.get_reports(self.user_id, report_type, symbol, limit=200)

        for row in self.tree.get_children():
            self.tree.delete(row)

        for r in reports:
            try:
                content = json.loads(r.content)
                if r.report_type == 'parameter_adjustment':
                    text = f"{content['param_name']}: {content['old_value']} → {content['new_value']} ({content['reason']})"
                elif r.report_type == 'loss_analysis':
                    text = f"亏损 {content['pnl']:.2f} USDT, 错误类型: {content['error_type']}, 原因: {content['exit_reason']}"
                else:
                    text = f"盈利 {content['pnl']:.2f} USDT"
                self.tree.insert("", tk.END, values=(
                    r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    r.report_type,
                    r.symbol or "-",
                    text[:200]
                ))
            except:
                pass