# 文件路径: gui/admin_window.py
import tkinter as tk
from tkinter import ttk, messagebox
from dao.user_dao import UserDAO
from services.auth_service import hash_password
from models.user import User

class AdminWindow:
    def __init__(self, current_user_id, logout_callback=None):
        self.current_user_id = current_user_id
        self.logout_callback = logout_callback
        self.root = tk.Toplevel()
        self.root.title("用户管理")
        self.root.geometry("600x400")
        self.create_widgets()
        self.load_users()
        self.root.mainloop()

    def create_widgets(self):
        toolbar = tk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        tk.Button(toolbar, text="添加用户", command=self.add_user).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="编辑用户", command=self.edit_user).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="删除用户", command=self.delete_user).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="刷新", command=self.load_users).pack(side=tk.LEFT, padx=2)

        columns = ("ID", "用户名", "管理员", "状态", "创建时间")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings", height=15)
        self.tree.heading("ID", text="ID")
        self.tree.heading("用户名", text="用户名")
        self.tree.heading("管理员", text="管理员")
        self.tree.heading("状态", text="状态")
        self.tree.heading("创建时间", text="创建时间")
        self.tree.column("ID", width=50)
        self.tree.column("用户名", width=150)
        self.tree.column("管理员", width=80)
        self.tree.column("状态", width=80)
        self.tree.column("创建时间", width=150)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def load_users(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        users = UserDAO.get_all()
        for user in users:
            is_admin = "是" if user.is_admin else "否"
            is_active = "正常" if user.is_active else "禁用"
            self.tree.insert("", tk.END, values=(
                user.id,
                user.username,
                is_admin,
                is_active,
                user.created_at.strftime("%Y-%m-%d %H:%M") if user.created_at else ""
            ))

    def add_user(self):
        UserEditDialog(self.root, self)

    def edit_user(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个用户")
            return
        item = self.tree.item(selected[0])
        user_id = item['values'][0]
        UserEditDialog(self.root, self, user_id)

    def delete_user(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个用户")
            return
        item = self.tree.item(selected[0])
        user_id = item['values'][0]
        username = item['values'][1]
        if user_id == self.current_user_id:
            messagebox.showerror("错误", "不能删除当前登录的管理员账户")
            return
        if messagebox.askyesno("确认", f"确定要删除用户 {username} 吗？"):
            UserDAO.delete(user_id)
            self.load_users()

class UserEditDialog:
    def __init__(self, parent, admin_window, user_id=None):
        self.parent = parent
        self.admin_window = admin_window
        self.user_id = user_id
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("编辑用户" if user_id else "添加用户")
        self.dialog.geometry("300x250")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.create_widgets()
        if user_id:
            self.load_user()
        self.dialog.wait_window()

    def create_widgets(self):
        tk.Label(self.dialog, text="用户名:").pack(pady=5)
        self.entry_username = tk.Entry(self.dialog)
        self.entry_username.pack()

        tk.Label(self.dialog, text="密码:").pack(pady=5)
        self.entry_password = tk.Entry(self.dialog, show="*")
        self.entry_password.pack()

        self.is_admin_var = tk.BooleanVar()
        tk.Checkbutton(self.dialog, text="管理员", variable=self.is_admin_var).pack()

        self.is_active_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.dialog, text="启用", variable=self.is_active_var).pack()

        btn_frame = tk.Frame(self.dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="确定", command=self.save).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def load_user(self):
        user = UserDAO.get_by_id(self.user_id)
        if user:
            self.entry_username.insert(0, user.username)
            self.is_admin_var.set(user.is_admin)
            self.is_active_var.set(user.is_active)
            self.entry_password.config(state='disabled')

    def save(self):
        username = self.entry_username.get().strip()
        password = self.entry_password.get().strip()
        is_admin = self.is_admin_var.get()
        is_active = self.is_active_var.get()

        if not username:
            messagebox.showerror("错误", "用户名不能为空")
            return

        if self.user_id:
            user = UserDAO.get_by_id(self.user_id)
            if not user:
                messagebox.showerror("错误", "用户不存在")
                return
            existing = UserDAO.get_by_username(username)
            if existing and existing.id != self.user_id:
                messagebox.showerror("错误", "用户名已存在")
                return
            user.username = username
            user.is_admin = is_admin
            user.is_active = is_active
            if password:
                user.password_hash = hash_password(password)
            UserDAO.update(user)
        else:
            if UserDAO.get_by_username(username):
                messagebox.showerror("错误", "用户名已存在")
                return
            if not password:
                messagebox.showerror("错误", "密码不能为空")
                return
            user = User(
                username=username,
                password_hash=hash_password(password),
                is_admin=is_admin,
                is_active=is_active
            )
            UserDAO.create(user)

        self.admin_window.load_users()
        self.dialog.destroy()