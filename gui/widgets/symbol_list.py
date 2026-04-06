# 文件路径: gui/widgets/symbol_list.py
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Callable
from services.portfolio_service import PortfolioService
from services.platform_service import PlatformService

class SymbolList(ttk.Frame):
    def __init__(self, parent, key_service, on_select_callback: Callable, log_callback: Optional[Callable] = None):
        super().__init__(parent)
        self.key_service = key_service
        self.user_id = key_service.user_id
        self.on_select_callback = on_select_callback
        self.log_callback = log_callback
        self.selected_key_id = None
        self.selected_symbol = None
        self.portfolio_service = PortfolioService()
        self.platform_service = PlatformService()
        style = ttk.Style(); style.theme_use('clam')
        style.configure('Treeview', background='white', foreground='black', fieldbackground='white', rowheight=25)
        style.configure('Treeview.Heading', font=('微软雅黑', 9, 'bold'), background='#f0f0f0', foreground='black')
        self.create_widgets()
        self.tree_menu = tk.Menu(self, tearoff=0)
        self.tree_menu.add_command(label='停止', command=self.stop_selected)
        self.tree_menu.add_command(label='删除', command=self.remove_selected)
        self.tree_menu.add_command(label='强制卖出', command=self.force_sell_selected)

    def create_widgets(self):
        input_frame = ttk.Frame(self); input_frame.pack(fill=tk.X, pady=5)
        ttk.Label(input_frame, text='交易币:', font=('微软雅黑', 10)).pack(side=tk.LEFT, padx=5)
        self.symbol_entry = ttk.Entry(input_frame, width=20); self.symbol_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(input_frame, text='添加币种', command=self.add_symbol).pack(side=tk.LEFT, padx=2)
        columns = ('币种', '状态', '模式', '持仓', '成本价', '最新价', '盈亏')
        self.tree = ttk.Treeview(self, columns=columns, show='headings', height=15, selectmode='browse')
        for col in columns:
            self.tree.heading(col, text=col); self.tree.column(col, width=100, minwidth=80, anchor=tk.CENTER)
        self.tree.column('币种', width=120); self.tree.column('持仓', width=120); self.tree.column('成本价', width=130); self.tree.column('最新价', width=130); self.tree.column('盈亏', width=150)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=5)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)
        self.tree.bind('<Button-3>', self._on_right_click)

    def set_key(self, key_id: int):
        self.selected_key_id = key_id
        if self.winfo_exists(): self.refresh()

    def refresh(self):
        if not self.winfo_exists() or not self.tree.winfo_exists() or not self.selected_key_id:
            return
        key = self.key_service.get_key(self.selected_key_id)
        if not key: return
        assets = key.get('assets', {})
        balances = key.get('last_balances', {})
        prices = key.get('last_prices', {})
        configured = set(key['symbols'].keys())
        expected_symbols = set(configured)
        for symbol, asset in assets.items():
            if asset.get('qty', 0) > 0:
                expected_symbols.add(symbol)
        current_items = {}
        for item in self.tree.get_children():
            values = self.tree.item(item, 'values')
            if values: current_items[values[0]] = item
        for symbol in sorted(expected_symbols):
            asset = assets.get(symbol)
            if asset:
                qty = float(asset.get('qty', 0) or 0)
                price = float(asset.get('price', 0) or 0)
                cost = float(asset.get('cost', 0) or 0)
            else:
                base_coin = symbol.replace('USDT', '')
                qty = float(balances.get(base_coin, 0.0) or 0.0)
                price = float(prices.get(symbol, 0) or 0)
                cfg = key['symbols'].get(symbol, {})
                cost = float(cfg.get('avg_price') or 0)
            if symbol in configured:
                bot_status = self.key_service.get_bot_status(self.selected_key_id, symbol)
                if bot_status and bot_status['running']:
                    status = '运行中'; mode = bot_status['mode_display']; pos = bot_status['position']
                    if pos['has_position']:
                        qty = pos['qty']; cost = pos['avg_price']
                else:
                    status = '停止'; mode = key['symbols'].get(symbol, {}).get('mode', '-')
            else:
                status = '持仓' if qty > 0 else '未持仓'; mode = '-'
            pnl_usdt = self.portfolio_service.calc_unrealized_pnl(qty, cost, price, key.get('platform','bybit')) if qty and cost and price else 0.0
            pnl_pct = ((price - cost) / cost * 100) if cost and price else 0.0
            qty_str = f'{qty:.4f}' if qty > 0 else '0'
            price_str = f'{price:.6f}' if price > 0 else '-'
            cost_str = f'{cost:.6f}' if cost > 0 else '-'
            pnl_str = f'{pnl_usdt:.2f} ({pnl_pct:.2f}%)' if (pnl_usdt != 0 or pnl_pct != 0) else '0.00 (0.00%)'
            new_values = (symbol, status, mode, qty_str, cost_str, price_str, pnl_str)
            if symbol in current_items and current_items[symbol]:
                self.tree.item(current_items[symbol], values=new_values)
            else:
                iid = self.tree.insert('', tk.END, values=new_values)
                current_items[symbol] = iid
        for symbol, item in list(current_items.items()):
            if symbol not in expected_symbols and item:
                self.tree.delete(item)
        if self.selected_symbol and self.selected_symbol in current_items and current_items[self.selected_symbol]:
            try:
                self.tree.selection_set(current_items[self.selected_symbol]); self.tree.see(current_items[self.selected_symbol])
            except: pass
        else:
            self.selected_symbol = None; self.on_select_callback(None)

    def update_status_from_bot(self, symbol: str):
        try:
            for item_id in self.tree.get_children():
                values = self.tree.item(item_id, 'values')
                if not values: continue
                if values[0] != symbol: continue
                self.refresh(); break
        except Exception as e:
            print(f'[SymbolList] update_status_from_bot error: {e}')

    def get_selected_symbol(self) -> Optional[str]:
        if not self.tree.winfo_exists(): return None
        selected = self.tree.selection()
        if selected:
            values = self.tree.item(selected[0], 'values')
            return values[0] if values else None
        return None

    def _on_select(self, event):
        self.selected_symbol = self.get_selected_symbol(); self.on_select_callback(self.selected_symbol)

    def _on_right_click(self, event):
        if not self.tree.winfo_exists(): return
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            values = self.tree.item(item, 'values')
            if values:
                symbol = values[0]
                bot_status = self.key_service.get_bot_status(self.selected_key_id, symbol)
                self.tree_menu.entryconfig('停止', state=tk.NORMAL if bot_status and bot_status['running'] else tk.DISABLED)
                self.tree_menu.entryconfig('删除', state=tk.NORMAL)
                self.tree_menu.entryconfig('强制卖出', state=tk.NORMAL if values[3] != '0' else tk.DISABLED)
                self.tree_menu.post(event.x_root, event.y_root)

    def add_symbol(self):
        raw = self.symbol_entry.get().strip()
        if not raw: return
        self.event_generate('<<AddSymbol>>'); self.symbol_entry.delete(0, tk.END)

    def remove_selected(self):
        if not self.selected_key_id or not self.selected_symbol: return
        if messagebox.askyesno('确认', f'确定移除 {self.selected_symbol}？'):
            self.key_service.stop_bot(self.selected_key_id, self.selected_symbol)
            key = self.key_service.get_key(self.selected_key_id)
            if key and self.selected_symbol in key['symbols']:
                from dao.symbol_config_dao import SymbolConfigDAO
                db_id = key['symbols'][self.selected_symbol].get('db_id')
                if db_id: SymbolConfigDAO.delete(db_id)
                del key['symbols'][self.selected_symbol]
            self.refresh()
            if self.log_callback: self.log_callback(f'已移除 {self.selected_symbol}')

    def stop_selected(self):
        if not self.selected_key_id or not self.selected_symbol: return
        if self.key_service.stop_bot(self.selected_key_id, self.selected_symbol):
            self.refresh()
            if self.log_callback: self.log_callback(f'{self.selected_symbol} 已停止')
        else:
            if self.log_callback: self.log_callback(f'{self.selected_symbol} 未运行')

    def force_sell_selected(self):
        if not self.selected_key_id or not self.selected_symbol:
            messagebox.showwarning('警告', '请先选中币种'); return
        messagebox.showinfo('提示', '当前整合版保留原强制卖出入口，建议在实盘前先联调对应平台私有接口。')
