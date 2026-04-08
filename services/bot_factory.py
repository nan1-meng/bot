# 文件路径: services/bot_factory.py
def create_bot(platform, api_key, secret_key, symbol, config, user_id, key_id=None, key_service=None,
               mode_display="", callback=None, risk_manager=None):
    """
    根据配置创建对应的机器人实例
    risk_manager: 可选，共享的 RiskManager 实例（用于学习）
    """
    if config.get("scalping_mode"):
        from bots.scalping_bot import ScalpingBot
        return ScalpingBot(platform, api_key, secret_key, symbol, config, user_id, key_id, key_service,
                           mode_display, callback, risk_manager=risk_manager)
    elif "AI" in mode_display or "资深" in mode_display or "全局" in mode_display or "全自动" in mode_display:
        from bots.expert_bot import ExpertBot
        return ExpertBot(platform, api_key, secret_key, symbol, config, user_id, key_id, key_service,
                         mode_display, callback, risk_manager=risk_manager)
    else:
        from bots.strategy_bot import StrategyBot
        return StrategyBot(platform, api_key, secret_key, symbol, config, user_id, key_id, key_service,
                           mode_display, callback, risk_manager=risk_manager)