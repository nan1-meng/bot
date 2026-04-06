# 文件路径: main.py
import sys
import tkinter

from utils.db import init_db, migrate_database

# 抑制 Tkinter 变量析构时的 RuntimeError
def tkinter_variable_del_wrapper(method):
    def wrapped(self):
        try:
            method(self)
        except RuntimeError:
            pass
    return wrapped

tkinter.Variable.__del__ = tkinter_variable_del_wrapper(tkinter.Variable.__del__)

# 抑制 libpng 警告
if not hasattr(sys, '_libpng_warning_filter'):
    sys._libpng_warning_filter = True
    _stderr = sys.stderr
    class _FilteredStderr:
        def write(self, s):
            if 'libpng warning' not in s:
                _stderr.write(s)
        def flush(self):
            _stderr.flush()
    sys.stderr = _FilteredStderr()

from utils.db import init_db, Session
from gui.login_window import LoginWindow

if __name__ == '__main__':
    # 初始化数据库表
    init_db()
    # 自动迁移：添加缺失的列
    migrate_database()
    # 启动登录窗口
    LoginWindow()
    # 程序结束时关闭数据库连接
    Session.remove()