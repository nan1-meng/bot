# 文件路径: services/platform_service.py
from utils.platforms import get_platform_meta, get_supported_platforms

class PlatformService:
    def list_supported_platforms(self):
        return get_supported_platforms()
    def get_platform_meta(self, platform: str):
        return get_platform_meta(platform)
    def get_fee_rate(self, platform: str) -> float:
        meta = get_platform_meta(platform)
        return meta.taker_fee_rate if meta else 0.001
    def get_min_notional(self, platform: str) -> float:
        meta = get_platform_meta(platform)
        return meta.min_notional_usdt if meta else 5.0
    def get_safe_ops_per_sec(self, platform: str) -> int:
        meta = get_platform_meta(platform)
        if not meta:
            return 5
        return max(1, int(meta.api_rate_limit_per_sec * 0.5))
