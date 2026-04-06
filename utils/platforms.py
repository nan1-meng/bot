# 文件路径: utils/platforms.py
from dataclasses import dataclass
from typing import Dict, Optional, List

@dataclass
class PlatformMeta:
    name: str
    display_name: str
    taker_fee_rate: float
    maker_fee_rate: float
    api_rate_limit_per_sec: int
    min_notional_usdt: float
    qty_precision_default: int = 6
    price_precision_default: int = 6
    requires_passphrase: bool = False

PLATFORMS: Dict[str, PlatformMeta] = {
    'binance': PlatformMeta('binance','Binance',0.001,0.001,20,5.0),
    'bybit': PlatformMeta('bybit','Bybit',0.001,0.001,20,5.0),
    'bitget': PlatformMeta('bitget','Bitget',0.001,0.001,10,5.0, requires_passphrase=True),
    'gate': PlatformMeta('gate','Gate',0.001,0.001,10,5.0),
}

def get_supported_platforms() -> List[str]:
    return list(PLATFORMS.keys())

def get_platform_display_names() -> Dict[str, str]:
    return {k:v.display_name for k,v in PLATFORMS.items()}

def get_platform_meta(platform: str) -> Optional[PlatformMeta]:
    return PLATFORMS.get((platform or '').lower())

def split_secret_and_passphrase(secret_text: str):
    if not secret_text:
        return '', ''
    if '::' in secret_text:
        a,b = secret_text.split('::',1)
        return a.strip(), b.strip()
    if '|' in secret_text:
        a,b = secret_text.split('|',1)
        return a.strip(), b.strip()
    return secret_text.strip(), ''
