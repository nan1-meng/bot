# 文件路径: gui/widgets/log_panel.py
import tkinter as tk
from tkinter import ttk, scrolledtext
import time

class LogPanel(ttk.Frame):
    def __init__(self, parent, max_lines=100):
        super().__init__(parent)
        self.max_lines = max_lines
        self.create_widgets()
        self.auto_scroll = True

    def create_widgets(self):
        self.log_text = scrolledtext.ScrolledText(self, width=80, height=15, font=("微软雅黑", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.log_text.tag_configure("green", foreground="green")
        self.log_text.tag_configure("red", foreground="red")
        self.log_text.tag_configure("error", foreground="red")
        self.log_text.tag_configure("action", foreground="red")
        self.log_text.tag_configure("gold", foreground="gold")

        self.log_text.vbar.bind("<Button-1>", self._on_scroll)
        self.log_text.vbar.bind("<B1-Motion>", self._on_scroll)
        self.log_text.bind("<MouseWheel>", self._on_mousewheel)
        self.log_text.bind("<Configure>", self._on_configure)

    def _on_scroll(self, event):
        self._update_auto_scroll()

    def _on_mousewheel(self, event):
        self._update_auto_scroll()
        return None

    def _on_configure(self, event):
        self._update_auto_scroll()

    def _update_auto_scroll(self):
        try:
            pos = self.log_text.vbar.get()
            self.auto_scroll = (pos[1] >= 0.999)
        except:
            pass

    def log(self, msg, key_id=None):
        # 行数限制
        lines = int(self.log_text.index('end-1c').split('.')[0])
        if lines > self.max_lines:
            # 删除最前面的 50 行，避免一次删除太多
            delete_lines = lines - self.max_lines + 50
            self.log_text.delete(1.0, f"{delete_lines}.0")

        timestamp = time.strftime("%H:%M:%S")
        prefix = f"[{timestamp}]"
        if key_id:
            prefix += f"[{key_id}]"
        full_msg = f"{prefix} {msg}\n"

        self.log_text.insert(tk.END, full_msg)

        line_start = self.log_text.index("end-2c linestart")
        line_end = self.log_text.index("end-1c")
        if "错误" in msg or "失败" in msg or "异常" in msg:
            self.log_text.tag_add("error", line_start, line_end)
        elif "盈利" in msg or ("+" in msg and "净盈亏" in msg):
            self.log_text.tag_add("green", line_start, line_end)
        elif "亏损" in msg or ("-" in msg and "净盈亏" in msg):
            self.log_text.tag_add("red", line_start, line_end)
        if "买入" in msg or "卖出" in msg:
            self.log_text.tag_add("action", line_start, line_end)

        if self.auto_scroll:
            self.log_text.see(tk.END)