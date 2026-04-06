# 文件路径: test_init_db.py
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.db import init_db

if __name__ == '__main__':
    init_db()
    print("数据库初始化完成。")