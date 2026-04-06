# 文件路径: gui/trade_history_window.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
from collections import deque
import csv
from dao.trade_dao import TradeDAO
from dao.api_key_dao import ApiKeyDAO

class TradeHistoryWindow:
    def __init__(self, user_id, key_service, log_callback=None):
        self.user_id = user_id
        self.key_service = key_service
        self.log_callback = log_callback
        self.root = tk.Toplevel()
        self.root.title("交易记录")
        self.root.geometry("1000x650")

        self.current_displayed_ids = []
        self.trade_cache = {}  # 缓存交易对象，用于右键查看K线
        self.create_widgets()
        self.load_filters()
        self.load_data()
        self.root.mainloop()

    def create_widgets(self):
        filter_frame = ttk.LabelFrame(self.root, text="筛选条件", padding=5)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        row0 = ttk.Frame(filter_frame)
        row0.pack(fill=tk.X, pady=2)

        ttk.Label(row0, text="Key:").pack(side=tk.LEFT, padx=5)
        self.key_var = tk.StringVar(value="全部")
        self.key_combo = ttk.Combobox(row0, textvariable=self.key_var, width=20, state="readonly")
        self.key_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(row0, text="模式:").pack(side=tk.LEFT, padx=5)
        self.mode_var = tk.StringVar(value="全部")
        self.mode_combo = ttk.Combobox(row0, textvariable=self.mode_var, width=20, state="readonly")
        self.mode_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(row0, text="币种:").pack(side=tk.LEFT, padx=5)
        self.symbol_var = tk.StringVar(value="全部")
        self.symbol_combo = ttk.Combobox(row0, textvariable=self.symbol_var, width=15, state="readonly")
        self.symbol_combo.pack(side=tk.LEFT, padx=5)

        row1 = ttk.Frame(filter_frame)
        row1.pack(fill=tk.X, pady=2)

        ttk.Label(row1, text="方向:").pack(side=tk.LEFT, padx=5)
        self.side_var = tk.StringVar(value="全部")
        side_combo = ttk.Combobox(row1, textvariable=self.side_var, values=["全部", "买入", "卖出"], width=8, state="readonly")
        side_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(row1, text="时间范围:").pack(side=tk.LEFT, padx=5)
        self.time_range_var = tk.StringVar(value="全部")
        range_combo = ttk.Combobox(row1, textvariable=self.time_range_var, values=["全部", "今日", "本周", "本月", "自定义"], width=10, state="readonly")
        range_combo.pack(side=tk.LEFT, padx=5)
        range_combo.bind("<<ComboboxSelected>>", self.on_range_selected)

        self.start_date_entry = ttk.Entry(row1, width=12)
        self.end_date_entry = ttk.Entry(row1, width=12)
        self.start_date_entry.pack(side=tk.LEFT, padx=5)
        self.end_date_entry.pack(side=tk.LEFT, padx=5)
        self.start_date_entry.config(state="disabled")
        self.end_date_entry.config(state="disabled")
        ttk.Label(row1, text="起始:").pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="结束:").pack(side=tk.LEFT, padx=5)

        ttk.Button(row1, text="查询", command=self.load_data).pack(side=tk.LEFT, padx=10)

        table_frame = ttk.Frame(self.root)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 操作栏：全选、反选、删除选中、导出CSV
        action_frame = ttk.Frame(table_frame)
        action_frame.pack(fill=tk.X, pady=2)
        self.select_all_var = tk.BooleanVar()
        ttk.Checkbutton(action_frame, text="全选", variable=self.select_all_var, command=self.toggle_select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="反选", command=self.invert_selection).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="删除选中", command=self.delete_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="导出 CSV", command=self.export_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="刷新", command=self.load_data).pack(side=tk.LEFT, padx=5)

        # 表格列
        columns = ("ID", "时间", "平台", "币种", "方向", "价格", "数量", "成交额(USDT)", "手续费", "盈亏(USDT)", "订单号")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=20, selectmode="extended")
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, anchor=tk.CENTER)
        self.tree.column("ID", width=50)
        self.tree.column("时间", width=150)
        self.tree.column("平台", width=80)
        self.tree.column("币种", width=80)
        self.tree.column("方向", width=60)
        self.tree.column("价格", width=100)
        self.tree.column("数量", width=100)
        self.tree.column("成交额(USDT)", width=120)
        self.tree.column("手续费", width=100)
        self.tree.column("盈亏(USDT)", width=100)
        self.tree.column("订单号", width=150)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Button-3>", self.on_right_click)  # 右键菜单

        # 右键菜单
        self.right_click_menu = tk.Menu(self.root, tearoff=0)
        self.right_click_menu.add_command(label="查看买入K线", command=self.view_entry_kline)
        self.right_click_menu.add_command(label="查看卖出K线", command=self.view_exit_kline)

        # 状态栏
        self.status_var = tk.StringVar()
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=2)

    def on_right_click(self, event):
        """右键点击表格时弹出菜单"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            # 获取选中行的交易ID
            selected = self.tree.selection()
            if selected:
                values = self.tree.item(selected[0], "values")
                if values:
                    trade_id = int(values[0])
                    # 从缓存中获取交易对象
                    trade = self.trade_cache.get(trade_id)
                    if trade:
                        # 根据是否有K线数据启用菜单项
                        if trade.entry_kline:
                            self.right_click_menu.entryconfig("查看买入K线", state=tk.NORMAL)
                        else:
                            self.right_click_menu.entryconfig("查看买入K线", state=tk.DISABLED)
                        if trade.exit_kline:
                            self.right_click_menu.entryconfig("查看卖出K线", state=tk.NORMAL)
                        else:
                            self.right_click_menu.entryconfig("查看卖出K线", state=tk.DISABLED)
                        self.right_click_menu.post(event.x_root, event.y_root)

    def view_entry_kline(self):
        """查看买入K线快照"""
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0], "values")
        if not values:
            return
        trade_id = int(values[0])
        trade = self.trade_cache.get(trade_id)
        if trade and trade.entry_kline:
            self._show_kline(trade.entry_kline, f"买入快照 - {trade.symbol} @ {trade.price:.6f}")

    def view_exit_kline(self):
        """查看卖出K线快照"""
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0], "values")
        if not values:
            return
        trade_id = int(values[0])
        trade = self.trade_cache.get(trade_id)
        if trade and trade.exit_kline:
            self._show_kline(trade.exit_kline, f"卖出快照 - {trade.symbol} @ {trade.price:.6f}")

    def _show_kline(self, kline_data, title):
        """显示K线图窗口（支持中文字体）"""
        try:
            import matplotlib
            matplotlib.use('TkAgg')
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            # 设置中文字体
            plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
            plt.rcParams['axes.unicode_minus'] = False
        except ImportError:
            messagebox.showerror("错误", "请安装 matplotlib 库: pip install matplotlib")
            return

        # 解析K线数据
        prices = kline_data.get('prices', [])
        highs = kline_data.get('highs', [])
        lows = kline_data.get('lows', [])
        volumes = kline_data.get('volumes', [])
        timestamp = kline_data.get('timestamp', 0)

        if not prices:
            messagebox.showinfo("提示", "没有K线数据")
            return

        # 创建新窗口
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("800x500")

        # 创建图形
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 5), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
        fig.subplots_adjust(hspace=0)

        # 绘制K线（简化版：用折线图代替）
        ax1.plot(prices, color='black', linewidth=1, label='收盘价')
        ax1.fill_between(range(len(prices)), prices, alpha=0.3, color='blue')
        # 绘制高低点范围
        if highs and lows:
            for i in range(len(prices)):
                ax1.plot([i, i], [lows[i], highs[i]], color='gray', linewidth=0.5)

        ax1.set_title(f"{title} - 共{len(prices)}个周期")
        ax1.set_ylabel("价格 (USDT)")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # 成交量柱状图
        if volumes:
            ax2.bar(range(len(volumes)), volumes, color='gray', alpha=0.5)
            ax2.set_ylabel("成交量")
        ax2.set_xlabel("K线序号 (最新在右侧)")
        ax2.grid(True, alpha=0.3)

        # 将matplotlib图形嵌入Tkinter
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 关闭窗口时销毁图形对象，避免内存泄漏
        def on_close():
            plt.close(fig)
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

    def load_filters(self):
        keys = self.key_service.get_all_keys()
        key_options = ["全部"]
        for key_id in keys:
            key = self.key_service.get_key(key_id)
            if key:
                key_options.append(f"{key_id}: {key.get('platform', 'bybit').upper()}")
        self.key_combo["values"] = key_options
        self.key_combo.current(0)

        all_trades = TradeDAO.get_by_user(self.user_id, limit=10000)
        modes = set()
        for t in all_trades:
            mode_name = t.bot_mode
            if t.sub_mode:
                mode_name += f" ({t.sub_mode})"
            modes.add(mode_name)
        mode_options = ["全部"] + sorted(list(modes))
        self.mode_combo["values"] = mode_options
        self.mode_combo.current(0)

        symbols = set()
        for t in all_trades:
            symbols.add(t.symbol)
        symbol_options = ["全部"] + sorted(list(symbols))
        self.symbol_combo["values"] = symbol_options
        self.symbol_combo.current(0)

    def on_range_selected(self, event):
        selected = self.time_range_var.get()
        if selected == "自定义":
            self.start_date_entry.config(state="normal")
            self.end_date_entry.config(state="normal")
            self.start_date_entry.delete(0, tk.END)
            self.end_date_entry.delete(0, tk.END)
            self.start_date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
            self.end_date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        else:
            self.start_date_entry.config(state="disabled")
            self.end_date_entry.config(state="disabled")
            self.start_date_entry.delete(0, tk.END)
            self.end_date_entry.delete(0, tk.END)

    def load_data(self):
        selected_key = self.key_var.get()
        selected_mode = self.mode_var.get()
        selected_symbol = self.symbol_var.get()
        side = self.side_var.get()
        time_range = self.time_range_var.get()

        key_id_filter = None
        if selected_key != "全部":
            try:
                key_id_filter = int(selected_key.split(":")[0])
            except:
                pass

        mode_filter = None
        if selected_mode != "全部":
            mode_filter = selected_mode.split("(")[0].strip()

        start_dt = None
        end_dt = None
        if time_range == "今日":
            start_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = start_dt + timedelta(days=1) - timedelta(seconds=1)
        elif time_range == "本周":
            start_dt = datetime.now() - timedelta(days=datetime.now().weekday())
            start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = start_dt + timedelta(days=7) - timedelta(seconds=1)
        elif time_range == "本月":
            start_dt = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if start_dt.month == 12:
                end_dt = start_dt.replace(year=start_dt.year+1, month=1, day=1) - timedelta(seconds=1)
            else:
                end_dt = start_dt.replace(month=start_dt.month+1, day=1) - timedelta(seconds=1)
        elif time_range == "自定义":
            start_str = self.start_date_entry.get().strip()
            end_str = self.end_date_entry.get().strip()
            if start_str and end_str:
                try:
                    start_dt = datetime.strptime(start_str, "%Y-%m-%d")
                    end_dt = datetime.strptime(end_str, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
                except:
                    pass

        trades = TradeDAO.get_by_user(self.user_id, limit=10000)
        filtered = []
        for t in trades:
            if key_id_filter is not None and t.key_id != key_id_filter:
                continue
            if mode_filter is not None:
                full_mode = f"{t.bot_mode} ({t.sub_mode})" if t.sub_mode else t.bot_mode
                if full_mode != selected_mode:
                    continue
            if selected_symbol != "全部" and t.symbol != selected_symbol:
                continue
            if side != "全部" and t.side != side:
                continue
            if start_dt and t.timestamp < start_dt:
                continue
            if end_dt and t.timestamp > end_dt:
                continue
            filtered.append(t)

        filtered.sort(key=lambda x: x.timestamp)

        # 计算盈亏（FIFO）
        buy_queues = {}
        for t in filtered:
            symbol = t.symbol
            if t.side == "buy":
                if symbol not in buy_queues:
                    buy_queues[symbol] = deque()
                buy_queues[symbol].append((t.price, t.quantity))
            elif t.side == "sell":
                if symbol not in buy_queues or not buy_queues[symbol]:
                    continue
                sell_qty = t.quantity
                total_cost = 0.0
                matched_qty = 0.0
                while sell_qty > 0 and buy_queues[symbol]:
                    buy_price, buy_qty = buy_queues[symbol][0]
                    match_qty = min(sell_qty, buy_qty)
                    total_cost += buy_price * match_qty
                    matched_qty += match_qty
                    sell_qty -= match_qty
                    if buy_qty == match_qty:
                        buy_queues[symbol].popleft()
                    else:
                        buy_queues[symbol][0] = (buy_price, buy_qty - match_qty)
                revenue = t.price * matched_qty
                pnl = revenue - total_cost
                t.pnl = pnl
            else:
                t.pnl = 0.0

        for row in self.tree.get_children():
            self.tree.delete(row)

        total_pnl = 0.0
        self.current_displayed_ids = []
        self.trade_cache.clear()
        for t in filtered:
            pnl = getattr(t, 'pnl', 0.0)
            if pnl is None:
                pnl = 0.0
            total_pnl += pnl
            time_str = t.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            order_id_str = str(t.order_id) if t.order_id else ""
            item_id = self.tree.insert("", tk.END, values=(
                t.id,
                time_str,
                t.symbol,
                "买入" if t.side == "buy" else "卖出",
                f"{t.price:.6f}",
                f"{t.quantity:.4f}",
                f"{t.amount_usdt:.2f}",
                f"{t.fee:.6f}",
                f"{pnl:.2f}" if t.side == "sell" else "",
                order_id_str
            ))
            self.current_displayed_ids.append((item_id, t.id))
            self.trade_cache[t.id] = t  # 缓存交易对象

        self.status_var.set(f"共 {len(filtered)} 条记录，合计盈亏: {total_pnl:.2f} USDT")
        self.select_all_var.set(False)

    def on_tree_select(self, event):
        selected = self.tree.selection()
        all_items = self.tree.get_children()
        if len(selected) == len(all_items):
            self.select_all_var.set(True)
        else:
            self.select_all_var.set(False)

    def toggle_select_all(self):
        if self.select_all_var.get():
            self.tree.selection_set(self.tree.get_children())
        else:
            self.tree.selection_remove(self.tree.get_children())

    def invert_selection(self):
        all_items = self.tree.get_children()
        current_selection = set(self.tree.selection())
        new_selection = [item for item in all_items if item not in current_selection]
        self.tree.selection_set(new_selection)
        if len(new_selection) == len(all_items):
            self.select_all_var.set(True)
        else:
            self.select_all_var.set(False)

    def delete_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选中要删除的记录")
            return
        if not messagebox.askyesno("确认", f"确定删除选中的 {len(selected)} 条交易记录吗？此操作不可恢复。"):
            return
        for item in selected:
            trade_id = None
            for item_id, t_id in self.current_displayed_ids:
                if item_id == item:
                    trade_id = t_id
                    break
            if trade_id:
                TradeDAO.delete(trade_id)
        self.load_data()
        if self.log_callback:
            self.log_callback(f"已删除 {len(selected)} 条交易记录")

    def export_csv(self):
        items = self.tree.get_children()
        if not items:
            messagebox.showinfo("提示", "没有可导出的记录")
            return

        columns = [self.tree.heading(col)["text"] for col in self.tree["columns"]]
        default_filename = f"trade_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=default_filename
        )
        if not filename:
            return

        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                for item in items:
                    values = list(self.tree.item(item, "values"))
                    if len(values) > 9 and values[9]:
                        values[9] = f'="{values[9]}"'
                    writer.writerow(values)
            messagebox.showinfo("成功", f"已导出 {len(items)} 条记录到\n{filename}")
            if self.log_callback:
                self.log_callback(f"导出交易记录 {len(items)} 条")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))