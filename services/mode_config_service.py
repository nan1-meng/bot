# 文件路径: services/mode_config_service.py
import json
from dao.symbol_config_dao import SymbolConfigDAO
from models.symbol_config import SymbolConfig

class ModeConfigService:
    def save_mode_config(self, user_id, key_id, platform, symbol, mode, config):
        existing = SymbolConfigDAO.get_by_user_key_symbol(user_id, key_id, symbol, mode)
        if existing:
            existing.config_json = config
            existing.platform = platform
            SymbolConfigDAO.update(existing)
            return existing.id
        cfg = SymbolConfig(user_id=user_id, api_key_id=key_id, platform=platform, symbol=symbol, category='spot', mode=mode, config_json=config, is_active=True)
        return SymbolConfigDAO.create(cfg)

    def get_mode_config(self, user_id, key_id, platform, symbol, mode):
        existing = SymbolConfigDAO.get_by_user_key_symbol(user_id, key_id, symbol, mode)
        if not existing:
            return {}
        return existing.config_json or {}
