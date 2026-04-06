# 文件路径: gui/strategy_monitor_window.py
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from dao.strategy_params_dao import StrategyParamsDAO
from dao.coin_health_dao import CoinHealthDAO
from dao.coin_stats_dao import CoinStatsDAO
from dao.error_stats_dao import ErrorStatsDAO
from utils.db import Session
from models.strategy_params import StrategyParams  # 添加导入
from models.coin_health import CoinHealth
from models.coin_stats import CoinStats
from models.error_stats import ErrorStats

class StrategyMonitorWindow:
    def __init__(self, user_id, key_service):
        self.user_id = user_id
        self.key_service = key_service
        self.root = tk.Toplevel()
        self.root.title("策略监控 - 自循环状态与动态参数")
        self.root.geometry("1000x700")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.selected_key_id = None
        self.refresh_timer = None

        self.create_widgets()
        self.load_keys()
        self.start_refresh()
        self.root.mainloop()

    def create_widgets(self):
        # 顶部：Key选择
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(top_frame, text="选择Key:").pack(side=tk.LEFT, padx=5)
        self.key_combo = ttk.Combobox(top_frame, width=30, state="readonly")
        self.key_combo.pack(side=tk.LEFT, padx=5)
        self.key_combo.bind("<<ComboboxSelected>>", self.on_key_selected)

        ttk.Button(top_frame, text="刷新", command=self.refresh).pack(side=tk.LEFT, padx=5)

        # 笔记本
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 全局参数页
        self.global_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.global_frame, text="全局参数")

        # 币种参数页
        self.coins_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.coins_frame, text="币种参数")

        # 学习器状态页
        self.learner_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.learner_frame, text="学习器状态")

        # 创建各页内容
        self.create_global_page()
        self.create_coins_page()
        self.create_learner_page()

    def create_global_page(self):
        self.global_tree = ttk.Treeview(self.global_frame, columns=("param", "value"), show="headings", height=15)
        self.global_tree.heading("param", text="参数名")
        self.global_tree.heading("value", text="当前值")
        self.global_tree.column("param", width=200)
        self.global_tree.column("value", width=150)
        self.global_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_coins_page(self):
        columns = ("币种", "健康度", "止损倍数", "止盈倍数", "补仓次数限制", "总交易", "胜率", "最近错误")
        self.coins_tree = ttk.Treeview(self.coins_frame, columns=columns, show="headings", height=20)
        for col in columns:
            self.coins_tree.heading(col, text=col)
            self.coins_tree.column(col, width=100, anchor=tk.CENTER)
        self.coins_tree.column("币种", width=80)
        self.coins_tree.column("健康度", width=80)
        self.coins_tree.column("止损倍数", width=80)
        self.coins_tree.column("止盈倍数", width=80)
        self.coins_tree.column("补仓次数限制", width=100)
        self.coins_tree.column("总交易", width=80)
        self.coins_tree.column("胜率", width=80)
        self.coins_tree.column("最近错误", width=150)
        self.coins_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_learner_page(self):
        self.learner_text = tk.Text(self.learner_frame, wrap=tk.WORD, height=20)
        self.learner_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def load_keys(self):
        keys = self.key_service.get_all_keys()
        key_options = []
        for key_id in keys:
            key = self.key_service.get_key(key_id)
            if key:
                key_options.append(f"{key_id}: {key.get('platform', 'bybit').upper()}")
        self.key_combo['values'] = key_options
        if key_options:
            self.key_combo.current(0)
            self.on_key_selected()

    def on_key_selected(self, event=None):
        sel = self.key_combo.get()
        if not sel:
            return
        try:
            self.selected_key_id = int(sel.split(":")[0])
        except:
            return
        self.refresh()

    def refresh(self):
        if not self.selected_key_id:
            return
        self.refresh_global_params()
        self.refresh_coins_params()
        self.refresh_learner_status()

    def refresh_global_params(self):
        for item in self.global_tree.get_children():
            self.global_tree.delete(item)

        session = Session()
        try:
            # 直接使用 SQLAlchemy 查询，需要导入模型
            params = session.query(StrategyParams).filter(
                StrategyParams.user_id == self.user_id,
                StrategyParams.symbol.is_(None)
            ).all()
            for p in params:
                # 参数值可能是 JSON 字符串，尝试解析
                value = p.param_value
                if value and isinstance(value, str):
                    try:
                        import json
                        value = json.loads(value)
                        value = str(value)  # 显示为字符串
                    except:
                        pass
                self.global_tree.insert("", tk.END, values=(p.param_name, f"{value}"))

            defaults = {
                "stop_loss_atr_mult": 1.5,
                "take_profit_atr_mult": 1.0,
                "buy_threshold_base": 50,
                "position_ratio_base": 0.5,
                "add_position_max_times": 3,
                "min_position_ratio": 0.1,
                "max_position_ratio": 1.0,
            }
            existing = {p.param_name for p in params}
            for name, default in defaults.items():
                if name not in existing:
                    self.global_tree.insert("", tk.END, values=(name, f"{default:.4f} (默认)"))
        finally:
            session.close()

    def refresh_coins_params(self):
        for item in self.coins_tree.get_children():
            self.coins_tree.delete(item)

        session = Session()
        try:
            health_records = CoinHealthDAO.get_all_by_key(self.selected_key_id, session)
            health_dict = {r.symbol: r.health_score for r in health_records}

            coin_params = {}
            param_records = session.query(StrategyParams).filter(
                StrategyParams.key_id == self.selected_key_id,
                StrategyParams.symbol.isnot(None)
            ).all()
            for p in param_records:
                if p.symbol not in coin_params:
                    coin_params[p.symbol] = {}
                value = p.param_value
                if value and isinstance(value, str):
                    try:
                        import json
                        value = json.loads(value)
                    except:
                        pass
                coin_params[p.symbol][p.param_name] = value

            stats_records = session.query(CoinStats).filter_by(key_id=self.selected_key_id).all()
            stats_dict = {s.symbol: s for s in stats_records}

            error_records = ErrorStatsDAO.get_stats(self.selected_key_id)
            error_dict = {}
            for e in error_records:
                if e.symbol not in error_dict:
                    error_dict[e.symbol] = []
                error_dict[e.symbol].append(f"{e.error_type}({e.count})")

            all_symbols = set(health_dict.keys()) | set(coin_params.keys()) | set(stats_dict.keys())
            for symbol in sorted(all_symbols):
                health = health_dict.get(symbol, 60.0)
                stop_mult = coin_params.get(symbol, {}).get("stop_loss_atr_mult", "-")
                take_mult = coin_params.get(symbol, {}).get("take_profit_atr_mult", "-")
                add_max = coin_params.get(symbol, {}).get("add_position_max_times", "-")
                stats = stats_dict.get(symbol)
                total_trades = stats.total_trades if stats else 0
                win_rate = f"{stats.win_rate:.1f}%" if stats and stats.win_rate else "-"
                recent_errors = ", ".join(error_dict.get(symbol, []))[:100]
                self.coins_tree.insert("", tk.END, values=(
                    symbol,
                    f"{health:.1f}",
                    f"{stop_mult}" if stop_mult != "-" else "-",
                    f"{take_mult}" if take_mult != "-" else "-",
                    f"{add_max}" if add_max != "-" else "-",
                    total_trades,
                    win_rate,
                    recent_errors
                ))
        finally:
            session.close()

    def refresh_learner_status(self):
        self.learner_text.delete(1.0, tk.END)

        from dao.system_log_dao import SystemLogDAO
        logs = SystemLogDAO.get_logs(self.user_id, self.selected_key_id, level="INFO", limit=20)
        self.learner_text.insert(tk.END, "=== 最近学习调整记录 ===\n\n")
        for log in logs:
            if "在线学习" in log.message or "调整" in log.message:
                self.learner_text.insert(tk.END, f"[{log.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {log.message}\n")

        if not logs:
            self.learner_text.insert(tk.END, "暂无学习记录\n")

        self.learner_text.insert(tk.END, "\n=== 当前学习器状态 ===\n")
        learner = self.key_service.get_online_learner(self.selected_key_id)
        if learner and learner.running:
            last_analysis = datetime.fromtimestamp(learner.last_analysis) if learner.last_analysis else "未开始"
            next_analysis = datetime.fromtimestamp(learner.last_analysis + learner.analysis_interval) if learner.last_analysis else "未开始"
            self.learner_text.insert(tk.END, f"状态: 运行中\n")
            self.learner_text.insert(tk.END, f"分析间隔: {learner.analysis_interval} 秒\n")
            self.learner_text.insert(tk.END, f"上次分析: {last_analysis}\n")
            self.learner_text.insert(tk.END, f"下次分析: {next_analysis}\n")
        else:
            self.learner_text.insert(tk.END, "状态: 未启动\n")

    def start_refresh(self):
        self.refresh()
        self.refresh_timer = self.root.after(10000, self.start_refresh)

    def on_close(self):
        if self.refresh_timer:
            self.root.after_cancel(self.refresh_timer)
        self.root.destroy()