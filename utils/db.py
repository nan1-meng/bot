from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, scoped_session
from config import DATABASE_URI
import logging

logger = logging.getLogger(__name__)

engine = create_engine(
    DATABASE_URI,
    echo=False,
    pool_recycle=3600,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)
Session = scoped_session(sessionmaker(bind=engine))

def init_db():
    from models.base import Base
    Base.metadata.create_all(engine)
    print("数据库表创建成功！")

def migrate_database():
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if 'symbol_config' in tables:
        columns = [col['name'] for col in inspector.get_columns('symbol_config')]
        with engine.connect() as conn:
            new_columns = {
                'avg_price': 'FLOAT NULL',
                'quantity': 'FLOAT NULL',
                'source_type': "VARCHAR(20) NULL DEFAULT 'manual'",
                'is_pinned': 'BOOLEAN NULL DEFAULT 0',
                'auto_resume': 'BOOLEAN NULL DEFAULT 1',
                'is_hidden': 'BOOLEAN NULL DEFAULT 0',
                'runtime_state': 'VARCHAR(20) NULL',
                'last_position_value': 'FLOAT NULL',
            }
            for col_name, col_type in new_columns.items():
                if col_name not in columns:
                    try:
                        conn.execute(text(f"ALTER TABLE symbol_config ADD COLUMN {col_name} {col_type}"))
                    except Exception as e:
                        logger.warning(f"添加列 {col_name} 失败: {e}")
            conn.commit()

    if 'trade' in tables:
        columns = [col['name'] for col in inspector.get_columns('trade')]
        with engine.connect() as conn:
            new_columns = {
                'platform': 'VARCHAR(20) NULL',
                'is_manual': 'BOOLEAN NULL DEFAULT 0',
                'source_trade_id': 'VARCHAR(100) NULL',
                'entry_kline': 'JSON NULL',
                'exit_kline': 'JSON NULL',
                'highest_price': 'FLOAT NULL',
                'highest_time': 'DATETIME NULL',
                'lowest_price': 'FLOAT NULL',
                'lowest_time': 'DATETIME NULL',
                'add_records': 'JSON NULL',
            }
            for col_name, col_type in new_columns.items():
                if col_name not in columns:
                    try:
                        conn.execute(text(f"ALTER TABLE trade ADD COLUMN {col_name} {col_type}"))
                    except Exception as e:
                        logger.warning(f"添加列 {col_name} 失败: {e}")
            conn.commit()

    print("数据库迁移完成！")
