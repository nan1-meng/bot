# 文件路径: test_api_connection.py
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API 连接测试工具
用于测试 Bybit 和 Binance 的 API Key 是否能够正常连接并获取余额、价格等信息。
"""

import sys
import os

# 将项目根目录添加到 Python 路径（如果需要导入项目模块）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_client import BybitClient
from clients.binance_client import BinanceClient

def test_platform(platform, api_key, api_secret, testnet=False):
    """
    测试指定平台的 API 连接
    :param platform: 'bybit' 或 'binance'
    :param api_key: API Key
    :param api_secret: Secret Key
    :param testnet: 是否使用测试网（仅 Bybit 支持，Binance 测试网需要单独配置）
    :return: bool 是否成功
    """
    print(f"\n========== 测试 {platform.upper()} API 连接 ==========")
    print(f"API Key: {api_key[:8]}...{api_key[-4:] if len(api_key) > 12 else ''}")
    print(f"Testnet: {testnet}")

    try:
        if platform.lower() == 'bybit':
            client = BybitClient(api_key, api_secret, testnet=testnet, timeout=30)
        elif platform.lower() == 'binance':
            client = BinanceClient(api_key, api_secret, testnet=testnet, timeout=30)
        else:
            print(f"未知平台: {platform}")
            return False

        # 1. 测试获取余额
        print("\n1. 获取账户余额...")
        balances = client.get_balances()
        usdt_balance = 0.0
        other_balances = []
        for b in balances:
            coin = b.get('coin')
            available = b.get('availableToWithdraw', '0')
            if coin == 'USDT':
                usdt_balance = float(available) if available else 0.0
            elif float(available) > 0:
                other_balances.append(f"{coin}: {available}")
        print(f"   USDT 余额: {usdt_balance:.2f}")
        if other_balances:
            print(f"   其他非零余额: {', '.join(other_balances)}")
        else:
            print("   其他币种余额均为 0")

        # 2. 测试获取交易对信息（使用 BTCUSDT 作为示例）
        print("\n2. 获取交易对信息 (BTCUSDT)...")
        try:
            step, quote_decimals = client.get_symbol_info('BTCUSDT')
            print(f"   最小交易数量步长: {step}, 价格小数位数: {quote_decimals}")
        except Exception as e:
            print(f"   获取交易对信息失败: {e}")

        # 3. 测试获取实时价格
        print("\n3. 获取 BTCUSDT 实时价格...")
        try:
            price = client.get_ticker('BTCUSDT')
            print(f"   BTCUSDT 价格: {price:.2f}")
        except Exception as e:
            print(f"   获取价格失败: {e}")

        # 4. 测试获取 K 线数据
        print("\n4. 获取 BTCUSDT 1分钟 K 线 (最近5条)...")
        try:
            klines = client.get_klines('BTCUSDT', interval='1', limit=5)
            print(f"   成功获取 {len(klines)} 条 K 线")
            for k in klines:
                print(f"     时间: {k[0]}, 开盘: {k[1]}, 收盘: {k[4]}")
        except Exception as e:
            print(f"   获取 K 线失败: {e}")

        print(f"\n{platform.upper()} API 测试通过，所有核心接口均可用。")
        return True

    except Exception as e:
        print(f"\n{platform.upper()} API 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_user_input():
    """交互式获取用户输入的 API 凭证"""
    print("\n请输入 API 凭证进行测试（直接回车可跳过某项）：")
    platform = input("平台 (bybit/binance): ").strip().lower()
    if platform not in ['bybit', 'binance']:
        print("无效的平台，请重新运行并输入 bybit 或 binance")
        sys.exit(1)

    api_key = input("API Key: ").strip()
    if not api_key:
        print("API Key 不能为空")
        sys.exit(1)

    api_secret = input("Secret Key: ").strip()
    if not api_secret:
        print("Secret Key 不能为空")
        sys.exit(1)

    testnet_input = input("是否使用测试网？(y/N): ").strip().lower()
    testnet = testnet_input == 'y'

    return platform, api_key, api_secret, testnet


def main():
    print("=" * 60)
    print("API 连接测试工具")
    print("=" * 60)

    # 尝试从命令行参数获取
    if len(sys.argv) >= 4:
        platform = sys.argv[1].lower()
        api_key = sys.argv[2]
        api_secret = sys.argv[3]
        testnet = len(sys.argv) >= 5 and sys.argv[4].lower() == 'testnet'
        print("使用命令行参数")
    else:
        # 交互式输入
        platform, api_key, api_secret, testnet = get_user_input()

    success = test_platform(platform, api_key, api_secret, testnet)

    if success:
        print("\n测试完成，API 连接正常。")
        sys.exit(0)
    else:
        print("\n测试失败，请检查 API Key/Secret 是否正确，网络是否可访问交易所 API。")
        sys.exit(1)


if __name__ == "__main__":
    main()