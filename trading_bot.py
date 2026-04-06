# 文件路径: trading_bot.py
from services.bot_factory import create_bot

def TradingBot(api_key, secret_key, symbol, config, user_id, key_id=None, mode_display="", callback=None):
    return create_bot('bybit', api_key, secret_key, symbol, config, user_id, key_id, None, mode_display, callback)