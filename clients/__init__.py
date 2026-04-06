from .bybit_client import BybitClient
from .binance_client import BinanceClient
from .bitget_client import BitgetClient
from .gate_client import GateClient
from utils.platforms import split_secret_and_passphrase

def create_client(platform, api_key, api_secret, testnet=False, timeout=10):
    platform = (platform or '').lower()
    if platform == 'bybit':
        return BybitClient(api_key, api_secret, testnet, timeout)
    elif platform == 'binance':
        return BinanceClient(api_key, api_secret, testnet, timeout)
    elif platform == 'bitget':
        secret, passphrase = split_secret_and_passphrase(api_secret)
        return BitgetClient(api_key, secret, passphrase, testnet, timeout)
    elif platform == 'gate':
        return GateClient(api_key, api_secret, testnet, timeout)
    else:
        raise ValueError(f"Unsupported platform: {platform}")
