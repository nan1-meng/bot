# 文件路径: gui/widgets/key_list.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Callable, Optional
from utils.platforms import get_supported_platforms

class KeyList(ttk.Frame):
    def __init__(self, parent, key_service, on_select_callback: Callable, log_callback: Optional[Callable] = None):
        super().__init__(parent)
        self.key_service = key_service
        self.on_select_callback = on_select_callback
        self.log_callback = log_callback
        self._loading = False
        self.create_widgets()
        self.load_keys()
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label='修改Key名', command=self.modify_key)
        self.context_menu.add_command(label='删除Key', command=self.remove_key)

    def create_widgets(self):
        header = ttk.Label(self, text='API Keys', font=('微软雅黑', 10, 'bold'))
        header.pack(pady=(5, 0))
        self.tree = ttk.Treeview(self, columns=('key', 'balance'), show='headings', height=10)
        self.tree.heading('key', text='Key')
        self.tree.heading('balance', text='余额 (USDT)')
        self.tree.column('key', width=150)
        self.tree.column('balance', width=100)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=5)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)
        self.tree.bind('<Button-3>', self._on_right_click)
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text='添加Key', command=self.add_key).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text='刷新余额', command=self.refresh_balances).pack(side=tk.LEFT, padx=2)

    def load_keys(self):
        self._loading = True
        from dao.api_key_dao import ApiKeyDAO
        for item in self.tree.get_children():
            self.tree.delete(item)
        for key_id in self.key_service.get_all_keys():
            key = self.key_service.get_key(key_id)
            if key:
                platform = key.get('platform', 'bybit').upper()
                db_key = ApiKeyDAO.get_by_id(key_id)
                key_name = db_key.key_name if db_key else f'Key_{key_id}'
                usdt_balance = key.get('last_balances', {}).get('USDT', None)
                balance_display = '--' if usdt_balance is None else f'{usdt_balance:.2f}'
                self.tree.insert('', tk.END, iid=key_id, values=(f'{platform}:{key_name}', balance_display))
        self.tree.selection_remove(self.tree.selection())
        self.after_idle(lambda: self.tree.selection_remove(self.tree.selection()))
        self._loading = False

    def update_balance(self, key_id: int, total_usdt: float):
        try:
            if self.tree.exists(key_id):
                current_values = self.tree.item(key_id, 'values')
                key_display = current_values[0] if current_values else f'Key_{key_id}'
                self.tree.item(key_id, values=(key_display, f'{total_usdt:.2f}'))
            else:
                self.load_keys()
        except tk.TclError:
            pass

    def refresh_balances(self):
        selected = self.get_selected_key()
        for key_id in self.key_service.get_all_keys():
            new_balance = self.key_service.refresh_key_balance(key_id)
            self.update_balance(key_id, new_balance)
            if self.log_callback:
                self.log_callback(f'Key {key_id} 余额已刷新: {new_balance:.2f} USDT')
        self.load_keys()
        if selected:
            try: self.tree.selection_set(selected)
            except: pass

    def get_selected_key(self):
        selected = self.tree.selection()
        return int(selected[0]) if selected else None

    def _on_select(self, event):
        if self._loading:
            return
        selected = self.get_selected_key()
        if selected is not None:
            self.on_select_callback(selected)

    def _on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def add_key(self):
        dialog = tk.Toplevel(self)
        dialog.title('添加API Key')
        dialog.geometry('420x260')
        dialog.transient(self)
        dialog.grab_set()
        dialog.update_idletasks()
        x = self.winfo_toplevel().winfo_x() + (self.winfo_toplevel().winfo_width() - dialog.winfo_width()) // 2
        y = self.winfo_toplevel().winfo_y() + (self.winfo_toplevel().winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f'+{x}+{y}')
        ttk.Label(dialog, text='平台:').grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        platform_var = tk.StringVar(value='bybit')
        platform_combo = ttk.Combobox(dialog, textvariable=platform_var, values=get_supported_platforms(), state='readonly', width=20)
        platform_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Label(dialog, text='Key标识:').grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        key_id_entry = ttk.Entry(dialog, width=30)
        key_id_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(dialog, text='API Key:').grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        api_entry = ttk.Entry(dialog, width=30)
        api_entry.grid(row=2, column=1, padx=5, pady=5)
        ttk.Label(dialog, text='Secret Key:').grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        secret_entry = ttk.Entry(dialog, width=30, show='*')
        secret_entry.grid(row=3, column=1, padx=5, pady=5)
        ttk.Label(dialog, text='Bitget 可填 secret::passphrase').grid(row=4, column=1, padx=5, pady=0, sticky=tk.W)
        def on_ok():
            platform = platform_var.get(); key_name = key_id_entry.get().strip(); api = api_entry.get().strip(); secret = secret_entry.get().strip()
            if not platform or not key_name or not api or not secret:
                messagebox.showerror('错误', '所有字段都必须填写'); return
            new_id = self.key_service.add_key(platform, key_name, api, secret)
            if new_id:
                self.load_keys()
                if self.log_callback: self.log_callback(f'已添加Key: {platform.upper()} {key_name}')
                dialog.destroy()
            else:
                messagebox.showerror('错误', '添加失败，可能Key标识已存在')
        ttk.Button(dialog, text='确定', command=on_ok).grid(row=5, column=0, pady=10)
        ttk.Button(dialog, text='取消', command=dialog.destroy).grid(row=5, column=1, pady=10)

    def modify_key(self):
        key_id = self.get_selected_key()
        if not key_id:
            messagebox.showwarning('警告', '请先选中要修改的Key'); return
        from dao.api_key_dao import ApiKeyDAO
        db_key = ApiKeyDAO.get_by_id(key_id)
        if not db_key:
            messagebox.showerror('错误', 'Key不存在'); return
        current_name = db_key.key_name
        new_name = simpledialog.askstring('修改Key名', '请输入新的Key标识:', initialvalue=current_name, parent=self)
        if new_name and new_name.strip():
            db_key.key_name = new_name.strip(); ApiKeyDAO.update(db_key); self.load_keys()
            if self.log_callback: self.log_callback(f'Key标识已修改为: {new_name.strip()}')

    def remove_key(self):
        key_id = self.get_selected_key()
        if not key_id:
            messagebox.showwarning('警告', '请先选中要删除的Key'); return
        if messagebox.askyesno('确认', f'确定删除Key？'):
            if self.key_service.remove_key(key_id):
                self.load_keys()
                if self.log_callback: self.log_callback('已删除Key')
