# 文件路径: add_platform_keyname_to_trade.py
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.db import engine, Session
from sqlalchemy import text, inspect

def migrate():
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('trade')]
    with engine.connect() as conn:
        if 'platform' not in columns:
            conn.execute(text("ALTER TABLE trade ADD COLUMN platform VARCHAR(20) NULL"))
        if 'key_name' not in columns:
            conn.execute(text("ALTER TABLE trade ADD COLUMN key_name VARCHAR(50) NULL"))
        conn.commit()
    print("迁移完成：添加 platform 和 key_name 字段")

if __name__ == '__main__':
    migrate()