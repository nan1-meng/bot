# 文件路径: config.py
import os

DATABASE_URI = 'mysql+pymysql://root:new_password@localhost/bybit_bot'
ENCRYPTION_KEY = 'ayfmvxVPCfWv0dA0wg6V2RFpRoBv9I4xzLXYYVjM1HA='  # 例如 'Z0YKi2X8QxJj...'
TESTNET = False

# 可选：回测配置
BACKTEST_DATA_PATH = os.path.join(os.path.dirname(__file__), 'backtest_data')