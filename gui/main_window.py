# 文件路径: gui/main_window.py
import tkinter as tk
from tkinter import ttk, messagebox
from services.key_service import KeyService
from gui.widgets.key_list import KeyList
from gui.widgets.symbol_list import SymbolList
from gui.widgets.config_panel import ConfigPanel
from gui.widgets.log_panel import LogPanel
from utils.widgets import ScrollableFrame
from gui.admin_window import AdminWindow
from gui.trade_history_window import TradeHistoryWindow
from dao.system_log_dao import SystemLogDAO
import gc

class MainWindow:
    def __init__(self, user, parent):
        self.user = user
        self.parent = parent
        self.root = tk.Toplevel(parent)
        self.root.title(f"交易机器人 - 用户 {user.username}")
        self.root.geometry("1200x800")

        self.key_service = KeyService(user.id)
        self.selected_key_id = None
        self.selected_symbol = None
        self._refresh_timer = None

        self.create_menu()
        self.create_layout()
        self.start_monitors()
        self._start_refresh_timer()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        user_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="用户", menu=user_menu)
        user_menu.add_command(label="修改密码", command=self.change_password)
        user_menu.add_command(label="交易记录", command=self.open_trade_history)
        if self.user.is_admin:
            user_menu.add_separator()
            user_menu.add_command(label="用户管理", command=self.open_admin)
        user_menu.add_separator()
        user_menu.add_command(label="退出登录", command=self.logout)

        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="工具", menu=tools_menu)
        tools_menu.add_command(label="使用文档", command=self.open_help)
        tools_menu.add_command(label="历史日志", command=self.open_history_log)
        tools_menu.add_command(label="策略监控", command=self.open_strategy_monitor)
        tools_menu.add_command(label="学习报告", command=self.open_learning_report)

    def open_help(self):
        from gui.help_window import HelpWindow
        HelpWindow(self.root)

    def open_history_log(self):
        from gui.history_log_window import HistoryLogWindow
        HistoryLogWindow(self.user.id, self.key_service, self.log)

    def open_strategy_monitor(self):
        from gui.strategy_monitor_window import StrategyMonitorWindow
        StrategyMonitorWindow(self.user.id, self.key_service)

    def open_learning_report(self):
        from gui.learning_report_window import LearningReportWindow
        LearningReportWindow(self.user.id, self.key_service)

    def change_password(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("修改密码")
        dialog.geometry("300x200")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        tk.Label(dialog, text="原密码:").pack(pady=5)
        entry_old = tk.Entry(dialog, show="*")
        entry_old.pack()

        tk.Label(dialog, text="新密码:").pack(pady=5)
        entry_new = tk.Entry(dialog, show="*")
        entry_new.pack()

        tk.Label(dialog, text="确认新密码:").pack(pady=5)
        entry_confirm = tk.Entry(dialog, show="*")
        entry_confirm.pack()

        def on_ok():
            old = entry_old.get().strip()
            new = entry_new.get().strip()
            confirm = entry_confirm.get().strip()
            if not old or not new or not confirm:
                messagebox.showerror("错误", "所有字段都必须填写")
                return
            if new != confirm:
                messagebox.showerror("错误", "新密码与确认密码不一致")
                return
            from services.auth_service import change_password
            if change_password(self.user.id, old, new):
                messagebox.showinfo("成功", "密码修改成功，请重新登录")
                dialog.destroy()
                self.force_logout()
            else:
                messagebox.showerror("错误", "原密码错误")

        tk.Button(dialog, text="确定", command=on_ok).pack(pady=10)

    def logout(self):
        if messagebox.askyesno("确认", "确定要退出登录吗？"):
            self.force_logout()

    def force_logout(self):
        self._stop_refresh_timer()
        for key_id in self.key_service.get_all_keys():
            key = self.key_service.get_key(key_id)
            if key:
                for bot in key['bots'].values():
                    bot.stop()
        self.key_service.stop_all_monitor()
        self.root.destroy()
        self.parent.quit()

    def open_admin(self):
        AdminWindow(self.user.id, self.logout)

    def open_trade_history(self):
        TradeHistoryWindow(self.user.id, self.key_service, self.log)

    def create_layout(self):
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(main_paned, width=200)
        main_paned.add(left_frame, weight=1)
        self.key_list = KeyList(left_frame, self.key_service, self.on_key_selected, self.log)
        self.key_list.pack(fill=tk.BOTH, expand=True)

        middle_frame = ttk.Frame(main_paned)
        main_paned.add(middle_frame, weight=2)
        self.symbol_list = SymbolList(middle_frame, self.key_service, self.on_symbol_selected, self.log)
        self.symbol_list.pack(fill=tk.BOTH, expand=True)

        right_scroll = ScrollableFrame(main_paned)
        main_paned.add(right_scroll, weight=3)
        right_frame = right_scroll.scrollable_frame
        self.config_panel = ConfigPanel(right_frame, self.on_start_bot)
        self.config_panel.pack(fill=tk.BOTH, expand=True)

        log_frame = ttk.LabelFrame(right_frame, text="日志", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log_panel = LogPanel(log_frame, max_lines=100)
        self.log_panel.pack(fill=tk.BOTH, expand=True)

        self.symbol_list.bind("<<AddSymbol>>", self.on_add_symbol)

    def start_monitors(self):
        self.key_service.start_all_monitor(self.update_balance, self.update_prices)

    def update_balance(self, key_id, total_usdt):
        self.root.after(0, self._do_update_balance, key_id, total_usdt)

    def _do_update_balance(self, key_id, total_usdt):
        try:
            self.key_list.update_balance(key_id, total_usdt)
        except Exception as e:
            self.log(f"更新余额出错: {e}")

    def update_prices(self, key_id, prices):
        if key_id == self.selected_key_id:
            self.root.after(0, self.symbol_list.refresh)

    def on_key_selected(self, key_id):
        self.selected_key_id = key_id
        self.symbol_list.set_key(key_id)
        self.selected_symbol = None
        self.config_panel.set_key_service(self.key_service, key_id)
        self.config_panel.set_current_symbol(None)
        self.config_panel.clear_config()
        self.symbol_list.refresh()
        self._start_refresh_timer()
        # 更新全局模式按钮状态
        is_global_running = self.key_service.is_global_mode_running(key_id)
        self.config_panel.update_global_buttons(is_global_running)

    def on_symbol_selected(self, symbol):
        self.selected_symbol = symbol
        self.config_panel.set_current_symbol(symbol)
        if self.selected_key_id and symbol:
            key = self.key_service.get_key(self.selected_key_id)
            if key and symbol in key['symbols']:
                config = key['symbols'][symbol]
                self.config_panel.set_config(config)
            else:
                self.config_panel.clear_config()
        self.config_panel.refresh_estimate()

    def on_start_bot(self, bot_type, config, mode_display=None):
        if not self.selected_key_id:
            self.log("请先选中 Key")
            return

        # 全局模式：不需要选择币种，直接启动全局服务
        if bot_type == "global":
            success = self.key_service.start_global_mode(self.selected_key_id, config, self.on_trade_signal)
            if success:
                self.log("全局模式已启动")
                self.config_panel.update_global_buttons(True)
            else:
                self.log("全局模式启动失败")
            return

        # 停止全局模式
        if bot_type == "global_stop":
            success = self.key_service.stop_global_mode(self.selected_key_id)
            if success:
                self.log("全局模式已停止")
                self.config_panel.update_global_buttons(False)
            else:
                self.log("全局模式停止失败")
            return

        # 其他模式需要选中币种
        if not self.selected_symbol:
            self.log("请先选中币种")
            return

        if bot_type == "strategy":
            success = self.key_service.start_bot(
                self.selected_key_id, self.selected_symbol, config, "策略模式", self.on_trade_signal
            )
            if success:
                self.log(f"{self.selected_symbol} 策略模式启动")
        elif bot_type == "expert":
            success = self.key_service.start_bot(
                self.selected_key_id, self.selected_symbol, config, mode_display, self.on_trade_signal
            )
            if success:
                self.log(f"{self.selected_symbol} {mode_display}启动")
        elif bot_type == "scalping":
            key = self.key_service.get_key(self.selected_key_id)
            if key:
                from clients import create_client
                client = create_client(key['platform'], key['api_key'], key['secret'], testnet=False, timeout=10)
                try:
                    price = client.get_ticker(self.selected_symbol)
                    if price is None:
                        self.log("获取价格失败，无法启动刷单模式")
                        return
                    scalping_config, reward_coin, reward_amount = self.config_panel.get_scalping_config(price)
                    if scalping_config:
                        success = self.key_service.start_bot(
                            self.selected_key_id, self.selected_symbol, scalping_config, "刷单模式",
                            self.on_trade_signal
                        )
                        if success:
                            self.log(f"{self.selected_symbol} 刷单模式启动")
                    else:
                        self.log("刷单参数无效")
                except Exception as e:
                    self.log(f"获取价格失败: {e}")
            else:
                self.log("Key 不存在")

    def on_add_symbol(self, event):
        if not self.selected_key_id:
            self.log("请先选择一个 Key")
            return
        raw = self.symbol_list.symbol_entry.get().strip()
        if not raw:
            self.log("请输入币种")
            return
        symbol = self.symbol_list._normalize_symbol(raw)
        try:
            config = self.config_panel.get_strategy_config()
        except ValueError as e:
            self.log(f"参数错误: {e}")
            return
        key = self.key_service.get_key(self.selected_key_id)
        if symbol in key['symbols']:
            self.log(f"{symbol} 已存在")
            return
        from models.symbol_config import SymbolConfig
        from utils.db import Session
        session = Session()
        try:
            new_config = SymbolConfig(
                user_id=self.user.id,
                api_key_id=self.selected_key_id,
                platform=key['platform'],
                symbol=symbol,
                category='spot',
                mode='default',
                config_json=config,
                is_active=True
            )
            session.add(new_config)
            session.commit()
            config['db_id'] = new_config.id
            key['symbols'][symbol] = config
            self.symbol_list.refresh()
            self.log(f"已添加 {symbol}")
        except Exception as e:
            session.rollback()
            self.log(f"添加失败: {e}")
        finally:
            session.close()

    def on_trade_signal(self, key_id, symbol, signal_type, price, timestamp, msg=None):
        self.root.after(0, self._do_trade_signal, key_id, symbol, signal_type, price, timestamp, msg)

    def _do_trade_signal(self, key_id, symbol, signal_type, price, timestamp, msg=None):
        if msg:
            self.log(msg, key_id=key_id)
        elif signal_type in ("买入", "卖出", "补仓"):
            self.log(f"{symbol} {signal_type} @ {price:.6f}", key_id=key_id)
        if key_id == self.selected_key_id and symbol == self.selected_symbol:
            self.symbol_list.update_status_from_bot(symbol)

    def log(self, msg, key_id=None):
        self.log_panel.log(msg, key_id)
        level = "INFO"
        category = "系统"
        if "错误" in msg or "失败" in msg or "异常" in msg:
            level = "ERROR"
        elif "警告" in msg:
            level = "WARNING"
        if "买入" in msg or "卖出" in msg or "补仓" in msg:
            category = "交易"
        if level != "INFO" or "启动" in msg or "停止" in msg:
            try:
                SystemLogDAO.add(self.user.id, key_id, level, category, msg)
            except Exception as e:
                print(f"写入日志失败: {e}")

    def _start_refresh_timer(self):
        if self._refresh_timer:
            self.root.after_cancel(self._refresh_timer)
        self._refresh_timer = self.root.after(5000, self._periodic_refresh)

    def _periodic_refresh(self):
        if self.selected_key_id:
            self.symbol_list.refresh()
        gc.collect()
        self._refresh_timer = self.root.after(5000, self._periodic_refresh)

    def _stop_refresh_timer(self):
        if self._refresh_timer:
            self.root.after_cancel(self._refresh_timer)
            self._refresh_timer = None

    def on_close(self):
        self._stop_refresh_timer()
        for key_id in self.key_service.get_all_keys():
            key = self.key_service.get_key(key_id)
            if key:
                for bot in key['bots'].values():
                    bot.stop()
        self.key_service.stop_all_monitor()
        self.root.destroy()
        self.parent.quit()