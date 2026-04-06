# 文件路径: gui/login_window.py
import tkinter as tk
from tkinter import messagebox
from services.auth_service import authenticate
from gui.main_window import MainWindow

class LoginWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("登录 - 交易机器人")
        width = 300
        height = 180
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.resizable(False, False)
        self.create_widgets()
        self.root.mainloop()

    def create_widgets(self):
        tk.Label(self.root, text="用户名", font=("微软雅黑", 10)).pack(pady=5)
        self.entry_username = tk.Entry(self.root, font=("微软雅黑", 10))
        self.entry_username.pack()
        self.entry_username.bind('<Return>', lambda e: self.login())

        tk.Label(self.root, text="密码", font=("微软雅黑", 10)).pack(pady=5)
        self.entry_password = tk.Entry(self.root, show="*", font=("微软雅黑", 10))
        self.entry_password.pack()
        self.entry_password.bind('<Return>', lambda e: self.login())

        tk.Button(self.root, text="登录", command=self.login, width=10).pack(pady=10)

    def login(self):
        username = self.entry_username.get().strip()
        password = self.entry_password.get().strip()
        if not username or not password:
            messagebox.showerror("错误", "用户名和密码不能为空")
            return
        user = authenticate(username, password)
        if user and user.is_active:
            try:
                self.root.withdraw()
                MainWindow(user, self.root)
            except Exception as e:
                self.root.deiconify()
                messagebox.showerror("启动失败", f"无法启动主窗口: {e}")
        else:
            messagebox.showerror("错误", "用户名或密码错误，或账户被禁用")