# 文件路径: services/global_mode_service.py
import threading
import time
import math
import traceback
import gc
import requests
from typing import Dict, Any, Optional, List, Tuple
from dao.global_skip_dao import GlobalSkipDAO
from clients import create_client
from core.indicators import Indicators
from core.risk_manager import RiskManager
from core.signal_engine import SignalEngine
from core.exit_strategy import ExitStrategy
from core.add_position import AddPositionLogic
from core.timeframe_analyzer import TimeframeAnalyzer
from bots.global_sell_bot import GlobalSellBot
import logging

logger = logging.getLogger(__name__)

class GlobalModeService(threading.Thread):
    def __init__(self, user_id, key_id, key_service, config, callback=None):
        super().__init__()
        self.user_id = user_id
        self.key_id = key_id
        self.key_service = key_service
        self.config = config.copy()
        self.callback = callback
        self.running = True
        self.daemon = True
        self.interval = 120
        self.heartbeat_interval = 30
        self.last_heartbeat = 0

        self.indicators = Indicators()
        self.signal_engine = SignalEngine()
        self.risk_manager = RiskManager(key_id, user_id)
        self.exit_strategy = ExitStrategy()
        self.add_position_logic = AddPositionLogic()
        self.timeframe_analyzer = TimeframeAnalyzer()

        self.max_buy_amount = config.get("max_buy_amount")
        self.max_add_amount = config.get("max_add_amount")
        self.min_order_value = config.get("min_order_value", 5.0)
        self.slippage = config.get("slippage", 0.001)

        self.candidate_pool = []
        self.pool_last_update = 0
        self.pool_update_interval = 7200
        self.all_usdt_symbols = []
        self.cache_time = 0
        self.cache_duration = 3600

        self.market_trend = "neutral"
        self.market_volatility = 0.0
        self.last_market_update = 0
        self.market_update_interval = 300

        # 从配置中读取最大持仓数，默认3
        self.max_positions = config.get("max_positions", 3)
        self.batch_size = 20

        # 启动时清空该 Key 的所有跳过记录
        GlobalSkipDAO.clear_skipped(self.user_id, self.key_id)
        self.log("全局买入服务线程启动（自适应动态策略）")

    def log(self, msg):
        try:
            if self.callback:
                self.callback(self.key_id, None, "系统", 0, time.time(), msg=msg)
            else:
                print(msg)
        except Exception as e:
            print(f"日志回调失败: {e}")
            print(msg)

    def run(self):
        self.log("全局买入服务线程启动")
        while self.running:
            now = time.time()
            if now - self.last_heartbeat >= self.heartbeat_interval:
                self.last_heartbeat = now
                self.log("全局模式心跳")
            try:
                self._update_market_state()
                self._refresh_candidate_pool()
                self._scan_and_trade()
                gc.collect()
            except Exception as e:
                self.log(f"扫描异常: {e}\n{traceback.format_exc()}")
                logger.exception(e)
            time.sleep(self.interval)

    def stop(self):
        self.running = False

    def _update_market_state(self):
        now = time.time()
        if now - self.last_market_update < self.market_update_interval:
            return
        self.last_market_update = now
        try:
            client = self.key_service.get_client(self.key_id)
            if not client:
                return
            klines = client.get_klines("BTCUSDT", interval='60', limit=100)
            if not klines:
                return
            closes = [k[4] for k in klines]
            highs = [k[2] for k in klines]
            lows = [k[3] for k in klines]
            sma20 = self.indicators.sma(closes, 20)
            sma50 = self.indicators.sma(closes, 50)
            if sma20 and sma50:
                if sma20 > sma50 * 1.02:
                    self.market_trend = "bull"
                elif sma20 < sma50 * 0.98:
                    self.market_trend = "bear"
                else:
                    self.market_trend = "neutral"
            atr = self.signal_engine.calculate_atr(highs, lows, 14)
            current_price = closes[-1]
            self.market_volatility = atr / current_price if current_price != 0 else 0
            self.log(f"市场状态更新: 趋势={self.market_trend}, 波动率={self.market_volatility:.4f}")
        except Exception as e:
            self.log(f"更新市场状态失败: {e}")

    def _get_dynamic_buy_threshold(self, symbol: str) -> float:
        health = self.risk_manager.get_health_score(symbol)
        adjustment = (60 - health) * 0.5
        threshold = 50 + adjustment
        if self.market_trend == 'bear':
            threshold += 15
        elif self.market_trend == 'bull':
            threshold -= 5
        if self.market_volatility > 0.03:
            threshold += 10
        return max(20, min(80, threshold))

    def _refresh_candidate_pool(self):
        now = time.time()
        if now - self.pool_last_update < self.pool_update_interval:
            return
        self.pool_last_update = now
        self.log("刷新候选币种池...")
        all_symbols = self._get_all_usdt_symbols()
        if not all_symbols:
            self.log("获取USDT交易对失败，候选池为空")
            return

        key = self.key_service.get_key(self.key_id)
        if not key:
            self.log("Key不存在，候选池刷新失败")
            return

        client = self.key_service.get_client(self.key_id)
        if not client:
            self.log("无法获取交易所客户端")
            return

        try:
            balances = client.get_balances()
            usdt_balance = 0.0
            for c in balances:
                if c.get("coin") == "USDT":
                    usdt_balance = float(c.get("availableToWithdraw", 0))
                    break
        except Exception as e:
            self.log(f"获取余额失败: {e}")
            return

        self.log(f"当前USDT余额: {usdt_balance:.2f}")
        if usdt_balance < self.min_order_value:
            self.log("USDT余额不足最小订单额，候选池为空")
            return

        # 统计变量
        total_symbols = len(all_symbols)
        skipped_existing = 0
        min_order_filtered = 0
        volume_filtered = 0
        price_range_filtered = 0
        passed = 0
        error_count = 0

        new_pool = []
        processed = 0
        for symbol in all_symbols:
            processed += 1
            if processed % 50 == 0:
                self.log(f"已处理 {processed}/{total_symbols} 个币种...")
            if symbol in key['symbols'] or symbol in key['bots']:
                skipped_existing += 1
                continue

            # 检查最小订单额
            try:
                step, _ = client.get_symbol_info(symbol)
                price = client.get_ticker(symbol)
                if not price:
                    continue
                min_order_value = step * price
                if min_order_value > usdt_balance:
                    min_order_filtered += 1
                    continue
            except Exception as e:
                error_count += 1
                continue

            # 检查成交量和波动率
            try:
                klines = client.get_klines(symbol, interval='60', limit=24)
                if len(klines) < 24:
                    continue
                volumes = [float(k[5]) for k in klines if len(k) > 5]
                avg_volume = sum(volumes) / len(volumes) if volumes else 0
                if avg_volume < 1_000_000:
                    volume_filtered += 1
                    continue
                highs = [k[2] for k in klines]
                lows = [k[3] for k in klines]
                price_range = (max(highs) - min(lows)) / price
                if price_range < 0.005:
                    price_range_filtered += 1
                    continue
            except Exception:
                error_count += 1
                continue

            passed += 1
            new_pool.append(symbol)
            if len(new_pool) >= 100:
                break

        self.log(f"候选币种过滤统计: 总数={total_symbols}, 已配置/运行中={skipped_existing}, 最小订单额不足={min_order_filtered}, 成交量不足={volume_filtered}, 波动不足={price_range_filtered}, 错误={error_count}, 通过={passed}")
        self.candidate_pool = new_pool
        self.log(f"候选币种池更新完成，共 {len(self.candidate_pool)} 个币种")

    def _get_all_usdt_symbols(self):
        now = time.time()
        if self.all_usdt_symbols and now - self.cache_time < self.cache_duration:
            return self.all_usdt_symbols
        try:
            key = self.key_service.get_key(self.key_id)
            platform = key['platform'] if key else 'bybit'
            if platform == 'bybit':
                url = "https://api.bybit.com/v5/market/instruments-info"
                params = {"category": "spot"}
                resp = requests.get(url, params=params, timeout=15)
                data = resp.json()
                if data.get("retCode") != 0:
                    self.log(f"获取交易对失败: {data.get('retMsg')}")
                    return []
                symbols = []
                for item in data["result"]["list"]:
                    symbol = item["symbol"]
                    if symbol.endswith("USDT"):
                        upper = symbol.upper()
                        if any(x in upper for x in ["BULL", "BEAR", "UP", "DOWN", "3L", "3S"]):
                            continue
                        symbols.append(symbol)
            elif platform == 'binance':
                resp = requests.get("https://api.binance.com/api/v3/exchangeInfo", timeout=15)
                data = resp.json()
                symbols = [s['symbol'] for s in data['symbols'] if s['symbol'].endswith('USDT') and s['status'] == 'TRADING']
            else:
                symbols = []
            self.all_usdt_symbols = symbols
            self.cache_time = now
            self.log(f"获取到 {len(symbols)} 个 USDT 交易对")
            return symbols
        except Exception as e:
            self.log(f"获取交易对列表失败: {e}\n{traceback.format_exc()}")
            return []

    def _scan_and_trade(self):
        if not self.candidate_pool:
            self.log("候选池为空，跳过扫描")
            return
        key = self.key_service.get_key(self.key_id)
        if not key:
            return

        client = self.key_service.get_client(self.key_id)
        if not client:
            self.log("无法获取交易所客户端")
            return

        try:
            balances = client.get_balances()
            usdt_balance = 0.0
            for c in balances:
                if c.get("coin") == "USDT":
                    usdt_balance = float(c.get("availableToWithdraw", 0))
                    break
        except Exception as e:
            self.log(f"获取余额失败: {e}")
            return

        if usdt_balance < self.min_order_value:
            self.log("USDT余额不足，跳过扫描")
            return

        current_positions = len([s for s in key['bots'] if key['bots'][s].running])
        if current_positions >= self.max_positions:
            self.log(f"已达最大持仓数 {self.max_positions}，跳过买入")
            return

        scored_symbols = []
        for symbol in self.candidate_pool:
            if symbol in key['symbols'] or symbol in key['bots']:
                continue
            try:
                klines_1m = client.get_klines(symbol, interval='1', limit=100)
                if len(klines_1m) < 50:
                    continue
                prices = [k[4] for k in klines_1m]
                highs = [k[2] for k in klines_1m]
                lows = [k[3] for k in klines_1m]
                volumes = [float(k[5]) for k in klines_1m if len(k) > 5]
                current_price = prices[-1]

                score = self._calculate_realtime_score(highs, lows, current_price, volumes=volumes)
                threshold = self._get_dynamic_buy_threshold(symbol)
                if score >= threshold:
                    scored_symbols.append((symbol, score, current_price))
            except Exception as e:
                self.log(f"评分 {symbol} 失败: {e}")
            if len(scored_symbols) % 10 == 0:
                gc.collect()

        scored_symbols.sort(key=lambda x: x[1], reverse=True)
        top_symbols = scored_symbols[:3]

        for symbol, buy_score, price in top_symbols:
            if current_positions >= self.max_positions:
                break
            try:
                balances2 = client.get_balances()
                usdt_balance2 = 0.0
                for c in balances2:
                    if c.get("coin") == "USDT":
                        usdt_balance2 = float(c.get("availableToWithdraw", 0))
                        break
                if usdt_balance2 < self.min_order_value:
                    break

                klines_60 = client.get_klines(symbol, interval='60', limit=100)
                klines_240 = client.get_klines(symbol, interval='240', limit=100)
                klines_D = client.get_klines(symbol, interval='D', limit=100)
                if klines_60 and klines_240 and klines_D:
                    self.timeframe_analyzer.update_cache(symbol, klines_60, klines_240, klines_D)
                higher_trend = self.timeframe_analyzer.get_higher_trend(symbol)
                if higher_trend == 'bear':
                    self.log(f"{symbol} 较高时间框架为熊市，跳过买入")
                    continue

                health = self.risk_manager.get_health_score(symbol)
                if health < 20:
                    continue

                position_ratio = self.risk_manager.get_position_ratio(symbol)
                base_amount = usdt_balance2 * 0.5 * position_ratio
                if self.max_buy_amount is not None:
                    base_amount = min(base_amount, self.max_buy_amount)
                klines_1m = client.get_klines(symbol, interval='1', limit=100)
                highs = [k[2] for k in klines_1m]
                lows = [k[3] for k in klines_1m]
                atr = self.signal_engine.calculate_atr(highs, lows, 14)
                if atr > 0 and price > 0:
                    vol_factor = min(1.0, atr / price * 5)
                    base_amount = base_amount * (1 - vol_factor * 0.5)
                buy_amount = max(self.min_order_value, base_amount)
                buy_amount = min(buy_amount, usdt_balance2)
                if buy_amount < self.min_order_value:
                    continue

                self.log(f"{symbol} 买入评分 {buy_score:.1f} >= {threshold:.1f}，准备买入 {buy_amount:.2f} USDT")
                order_id = client.market_buy(symbol, buy_amount)
                if not order_id:
                    continue
                time.sleep(2)
                new_balances = client.get_balances()
                base_coin = symbol.replace("USDT", "")
                new_qty = 0.0
                for c in new_balances:
                    if c.get("coin") == base_coin:
                        new_qty = float(c.get("availableToWithdraw", 0))
                        break
                if new_qty <= 0:
                    self.log(f"{symbol} 买入后未检测到持仓")
                    continue

                from models.symbol_config import SymbolConfig
                from dao.symbol_config_dao import SymbolConfigDAO
                from utils.db import Session
                session = Session()
                try:
                    new_config = SymbolConfig(
                        user_id=self.user_id,
                        api_key_id=self.key_id,
                        platform=key['platform'],
                        symbol=symbol,
                        category='spot',
                        mode='global',
                        config_json=self.config,
                        is_active=True
                    )
                    session.add(new_config)
                    session.commit()
                    db_id = new_config.id
                except Exception as e:
                    session.rollback()
                    self.log(f"保存配置失败: {e}")
                    return
                finally:
                    session.close()

                bot = GlobalSellBot(
                    platform=key['platform'],
                    api_key=key['api_key'],
                    secret_key=key['secret'],
                    symbol=symbol,
                    config=self.config,
                    user_id=self.user_id,
                    key_id=self.key_id,
                    key_service=self.key_service,
                    mode_display="全局模式",
                    callback=self.callback
                )
                bot.position["has_position"] = True
                bot.position["qty"] = new_qty
                bot.position["avg_price"] = buy_amount / new_qty
                bot.position["entry_time"] = time.time()
                bot.start()

                with self.key_service._lock:
                    key = self.key_service.keys.get(self.key_id)
                    if key:
                        key['bots'][symbol] = bot
                        key['symbols'][symbol] = self.config
                        key['symbols'][symbol]['db_id'] = db_id
                self.log(f"{symbol} 买入成功，数量 {new_qty:.6f}，成本 {buy_amount/new_qty:.6f}")
                current_positions += 1
            except Exception as e:
                self.log(f"处理 {symbol} 失败: {e}")
            gc.collect()

    def _calculate_realtime_score(self, highs, lows, current_price, period=20, volumes=None):
        if len(highs) < period or len(lows) < period:
            return 0
        recent_high = max(highs[-period:])
        recent_low = min(lows[-period:])
        if recent_high == recent_low:
            return 0
        position_score = (current_price - recent_low) / (recent_high - recent_low) * 100
        if current_price > recent_high:
            breakout_extra = min(50, (current_price - recent_high) / recent_high * 500)
            position_score = min(100, position_score + breakout_extra)
        elif current_price < recent_low:
            pullback_extra = min(50, (recent_low - current_price) / recent_low * 500)
            position_score = min(100, position_score + pullback_extra)
        vol_factor = 1.0
        if volumes and len(volumes) >= period:
            avg_vol = sum(volumes[-period:]) / period
            if avg_vol > 0:
                vol_ratio = volumes[-1] / avg_vol
                if vol_ratio > 1.2:
                    vol_factor = 1.2
                elif vol_ratio < 0.8:
                    vol_factor = 0.8
        final_score = position_score * vol_factor
        return min(100, max(0, final_score))