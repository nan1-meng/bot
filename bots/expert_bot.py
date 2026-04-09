# ============================================================
# 文件: bots/expert_bot.py
# 说明: AI专家模式机器人，集成多策略切换和机器学习预测
# ============================================================

import time
import math
from collections import deque
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

from .base_bot import BaseBot
from services.trade_service import record_trade, start_bot_session, end_bot_session
from core.indicators import Indicators
from core.risk_manager import RiskManager
from core.signal_engine import SignalEngine
from core.exit_strategy import ExitStrategy
from core.add_position import AddPositionLogic
from core.timeframe_analyzer import TimeframeAnalyzer
from core.market_analyzer import MarketAnalyzer
from core.market_data_cache import MarketDataCache
from strategies.expert_rules import ExpertRules
from core.market_classifier import MarketClassifier
from strategies.strategy_switcher import StrategySwitcher
from core.ml_predictor import MLPredictor


class ExpertBot(BaseBot):
    def __init__(self, platform, api_key, secret_key, symbol, config, user_id, key_id, key_service,
                 mode_display="", callback=None, risk_manager=None):
        super().__init__(platform, api_key, secret_key, symbol, config, user_id, key_id,
                         mode_display, callback, auto_warmup=True, risk_manager=risk_manager)
        self.key_service = key_service
        self.indicators = Indicators()
        self.signal_engine = SignalEngine()
        self.exit_strategy = ExitStrategy()
        self.add_position_logic = AddPositionLogic()
        self.timeframe_analyzer = TimeframeAnalyzer()
        self.market_analyzer = MarketAnalyzer(lookback=50)
        self.expert_rules = ExpertRules()

        # 新增：市场分类器和策略切换器
        self.market_classifier = MarketClassifier()
        self.strategy_switcher = StrategySwitcher(config.get("strategy_switcher", {}))

        # 新增：机器学习预测器
        self.ml_predictor = MLPredictor(model_path=f"ml_models/{symbol}_{key_id}.pkl")
        self.ml_enabled = config.get("ml_enabled", True)

        self.kline_prices = deque(maxlen=500)
        self.kline_highs = deque(maxlen=500)
        self.kline_lows = deque(maxlen=500)
        self.kline_timestamps = deque(maxlen=500)
        self.volumes = deque(maxlen=500)

        self.tf_klines = {'60': None, '240': None, 'D': None}
        self.tf_last_update = 0
        self._add_fail_until = 0
        self.last_status_log = 0
        self.last_heartbeat = 0
        self.session_id = None
        self.entry_time = 0
        self.highest_price_since_entry = 0.0
        self.consecutive_losses = 0
        self.buy_blocked_until = 0
        self.buy_disabled = False
        self.add_count = 0
        self.last_add_price = 0.0

        self.min_order_value = self.config.get("min_order_value", 5.0)
        self.slippage = self.config.get("slippage", 0.001)
        self.max_buy_amount = self.config.get("max_buy_amount")
        self.max_add_amount = self.config.get("max_add_amount")

        self.entry_kline_snapshot = None
        self.highest_price = 0.0
        self.highest_time = 0
        self.lowest_price = 0.0
        self.lowest_time = 0
        self.add_records = []

        self.last_score_log_time = 0

        self.trade_fail_count = 0
        self.trade_fail_cooldown_until = 0
        self.last_action_reason = ""
        self.last_action = "hold"

        self.loop_interval = 2.0

        # 新增：卖出失败冷却
        self._sell_fail_until = 0
        self._sell_fail_count = 0
        self.MAX_SELL_FAIL = 3
        self.SELL_FAIL_COOLDOWN = 300

        self._warmup_kline()

        # 训练ML模型（如果历史数据足够）
        if self.ml_enabled:
            try:
                self.ml_predictor.train_from_history(self.symbol, self.key_id)
            except Exception as e:
                self._log("系统", f"ML模型训练失败: {e}")

    def _get_key_name(self) -> str:
        if self.key_service:
            key = self.key_service.get_key(self.key_id)
            if key:
                return key.get('key_name', str(self.key_id))
        return str(self.key_id)

    def _warmup_kline(self, minutes=100):
        try:
            self._log("系统", f"{self.symbol} 正在拉取历史K线数据预热({minutes}分钟)...")
            klines = self.client.get_klines(self.symbol, interval='1', limit=minutes)
            for k in klines:
                timestamp = k[0] // 1000
                high = k[2]
                low = k[3]
                close = k[4]
                volume = float(k[5]) if len(k) > 5 else 0
                self.kline_prices.append(close)
                self.kline_highs.append(high)
                self.kline_lows.append(low)
                self.kline_timestamps.append(timestamp)
                self.volumes.append(volume)
                self.update_kline(close, timestamp)
                self.market_analyzer.update(close, high, low, volume)
            self._log("系统", f"{self.symbol} 预热完成，已加载 {len(self.kline_prices)} 条1分钟K线")
        except Exception as e:
            self._log("系统", f"{self.symbol} 预热异常: {e}")

    def _update_timeframe_klines(self):
        now = time.time()
        if now - self.tf_last_update < 3600:
            return
        self.tf_last_update = now
        for tf in ['60', '240', 'D']:
            try:
                klines = self.client.get_klines(self.symbol, interval=tf, limit=100)
                self.tf_klines[tf] = klines
            except Exception as e:
                self._log("系统", f"{self.symbol} 获取{tf}K线失败: {e}")
        if self.tf_klines['60'] and self.tf_klines['240'] and self.tf_klines['D']:
            self.timeframe_analyzer.update_cache(
                self.symbol,
                self.tf_klines['60'],
                self.tf_klines['240'],
                self.tf_klines['D']
            )

    def _calculate_buy_score(self) -> float:
        """计算综合买入评分（融合技术指标、专家规则和ML预测）"""
        if len(self.kline_prices) < 50:
            return 0.0

        current_price = self.get_current_price()
        if current_price is None:
            current_price = self.kline_prices[-1] if self.kline_prices else 0

        highs = list(self.kline_highs)
        lows = list(self.kline_lows)
        volumes = list(self.volumes)
        prices = list(self.kline_prices)

        # 1. 技术指标评分
        range_score = self.signal_engine.realtime_range_score(highs, lows, current_price, period=20, volumes=volumes)

        # 2. 专家规则评分
        cache = MarketDataCache()
        features = cache.get_features(self.symbol)
        expert_score = self.expert_rules.evaluate(prices, highs, lows, current_price, features)
        expert_factor = 50 + expert_score * 50

        # 3. 机器学习预测概率
        ml_factor = 50.0
        if self.ml_enabled:
            ml_features = self.ml_predictor.extract_features(prices, volumes, highs, lows)
            if ml_features is not None:
                up_prob, down_prob = self.ml_predictor.predict(ml_features)
                ml_factor = up_prob * 100  # 上涨概率0~1转为0~100

        # 4. 根据市场状态调整权重
        market_state = self.strategy_switcher.current_state
        if market_state == "trending":
            weights = (0.3, 0.3, 0.4)  # ML权重更高
        elif market_state == "ranging":
            weights = (0.5, 0.3, 0.2)  # 技术指标权重更高
        else:
            weights = (0.4, 0.3, 0.3)

        final_score = (range_score * weights[0] + expert_factor * weights[1] + ml_factor * weights[2])
        return final_score

    def _get_dynamic_buy_threshold(self) -> float:
        base_threshold = self.risk_manager.get_param("buy_threshold_base", default=50)
        health = self.risk_manager.get_health_score(self.symbol)
        adjustment = (60 - health) * 0.5
        threshold = base_threshold + adjustment

        higher_trend = self.timeframe_analyzer.get_higher_trend(self.symbol)
        if higher_trend == 'bear':
            threshold += 10
        elif higher_trend == 'bull':
            threshold -= 5

        # 市场状态调整阈值
        market_state = self.strategy_switcher.current_state
        if market_state == "trending":
            threshold -= 5   # 趋势市场更容易买入
        elif market_state == "ranging":
            threshold += 5   # 震荡市场更谨慎

        market_state_info = self.market_analyzer.get_state()
        volatility = market_state_info.get('volatility_ratio', 0.01)
        if volatility > 0.03:
            threshold += 10
        elif volatility < 0.01:
            threshold -= 5

        volume_state = market_state_info.get('volume', 'normal')
        if volume_state == 'high':
            threshold += 5
        elif volume_state == 'low':
            threshold -= 5

        return max(20, min(80, threshold))

    def _calculate_atr(self) -> float:
        if len(self.kline_highs) < 14 or len(self.kline_lows) < 14:
            return 0.0
        highs = list(self.kline_highs)
        lows = list(self.kline_lows)
        return self.signal_engine.calculate_atr(highs, lows, 14)

    def _position_value(self, price: float) -> float:
        return (self.position["qty"] or 0.0) * (price or 0.0)

    def _has_tradable_position(self, price: float) -> bool:
        if not self.position["has_position"]:
            return False
        qty = self.position.get("qty", 0.0)
        if qty <= 0:
            return False
        value = qty * price
        return value >= self.min_order_value

    def _has_dust_position(self, price: float) -> bool:
        if not self.position["has_position"]:
            return False
        value = self._position_value(price)
        return 0 < value < self.min_order_value

    def _in_trade_cooldown(self) -> bool:
        return self.trade_fail_cooldown_until > time.time()

    def _record_trade_fail(self, reason: str):
        self.trade_fail_count += 1
        self.last_action = "blocked"
        self.last_action_reason = f"交易失败: {reason}"
        if self.trade_fail_count >= 3:
            self.trade_fail_cooldown_until = time.time() + 30
            self._log("系统", f"{self.symbol} 连续交易失败 {self.trade_fail_count} 次，进入30秒冷却")

    def _reset_trade_fail(self):
        self.trade_fail_count = 0
        self.trade_fail_cooldown_until = 0

    def _set_action(self, action: str, reason: str):
        self.last_action = action
        self.last_action_reason = reason

    # ========== 买入逻辑（融合策略切换） ==========
    def _should_buy(self, usdt_balance: float, price: float) -> bool:
        if self.buy_disabled:
            self._set_action("hold", "买入永久禁用")
            return False
        if self.buy_blocked_until > time.time():
            self._set_action("hold", "连续亏损触发买入冻结")
            return False
        if self._in_trade_cooldown():
            self._set_action("hold", "交易失败冷却中")
            return False

        with self._position_lock:
            if self.position["qty"] > 0:
                self._set_action("hold", f"已有持仓 {self.position['qty']:.4f}，禁止新开买入")
                return False

        higher_trend = self.timeframe_analyzer.get_higher_trend(self.symbol)
        if higher_trend == 'bear':
            self._set_action("hold", "大周期空头，禁止买入")
            return False

        # 使用策略切换器获取买入信号
        data = {
            "current_price": price,
            "usdt_balance": usdt_balance,
            "prices": list(self.kline_prices),
            "volumes": list(self.volumes),
            "highs": list(self.kline_highs),
            "lows": list(self.kline_lows)
        }
        should_buy_strategy, suggested_ratio = self.strategy_switcher.get_buy_signal(data)

        if should_buy_strategy:
            # 计算最终评分作为辅助验证
            score = self._calculate_buy_score()
            threshold = self._get_dynamic_buy_threshold()
            if score + 1e-6 < threshold:
                self._set_action("hold", f"买入评分不足 score={score:.1f} < threshold={threshold:.1f}")
                return False

            if usdt_balance < self.min_order_value:
                self._set_action("hold", f"USDT余额不足 {usdt_balance:.2f} < {self.min_order_value:.2f}")
                return False

            self._set_action("buy", f"策略信号买入, 市场状态={self.strategy_switcher.current_state}, 建议仓位={suggested_ratio:.2f}")
            return True

        self._set_action("hold", "策略信号不满足买入条件")
        return False

    def _calculate_buy_amount(self, usdt_balance: float, price: float) -> float:
        # 获取策略建议的仓位比例
        data = {
            "current_price": price,
            "usdt_balance": usdt_balance,
            "prices": list(self.kline_prices),
            "volumes": list(self.volumes),
            "highs": list(self.kline_highs),
            "lows": list(self.kline_lows)
        }
        _, suggested_ratio = self.strategy_switcher.get_buy_signal(data)

        health = self.risk_manager.get_health_score(self.symbol)
        position_ratio = self.risk_manager.get_position_ratio(self.symbol)

        # 结合策略建议和健康度
        final_ratio = min(suggested_ratio, position_ratio)
        base_amount = usdt_balance * final_ratio

        if self.max_buy_amount is not None:
            base_amount = min(base_amount, self.max_buy_amount)

        atr = self._calculate_atr()
        if atr > 0 and price > 0:
            vol_factor = min(1.0, atr / price * 5)
            base_amount = base_amount * (1 - vol_factor * 0.5)

        buy_amount = max(self.min_order_value, base_amount)
        buy_amount = min(buy_amount, usdt_balance)
        return buy_amount

    def _execute_buy(self, usdt_balance: float, price: float, now: float) -> bool:
        buy_amount = self._calculate_buy_amount(usdt_balance, price)
        if buy_amount < self.min_order_value:
            self._set_action("hold", f"买入金额不足 {buy_amount:.2f} < {self.min_order_value:.2f}")
            return False

        try:
            order_id = self.market_buy(buy_amount)
            if order_id is None:
                self._record_trade_fail("下单返回空order_id")
                return False

            time.sleep(2)
            new_balances = self.get_balances()
            new_base = new_balances[1]
            old_qty = self.position["qty"]

            if new_base <= old_qty:
                self._log("系统", f"{self.symbol} 买入后持仓未增加", price)
                self._record_trade_fail("买入后持仓未增加")
                return False

            actual_bought = new_base - old_qty
            if actual_bought <= 0:
                self._log("系统", f"{self.symbol} 买入后持仓未增加，可能未成交", price)
                self._record_trade_fail("买入实际成交数量<=0")
                return False

            buy_fee = buy_amount * self.slippage
            total_cost = buy_amount + buy_fee

            with self._position_lock:
                if old_qty == 0:
                    self.position["avg_price"] = total_cost / actual_bought
                else:
                    old_cost = self.position["avg_price"] * old_qty
                    new_total_cost = old_cost + total_cost
                    total_qty = new_base
                    if total_qty != 0:
                        self.position["avg_price"] = new_total_cost / total_qty
                self.position["qty"] = new_base
                self.position["has_position"] = True
                self.position["entry_time"] = now
                self.position["highest_price"] = price
                self.position["last_trade_time"] = now
                self.entry_time = now
                self.highest_price_since_entry = price
                self.add_count = 0
                self.last_add_price = price

            self.entry_kline_snapshot = {
                'prices': list(self.kline_prices)[-20:],
                'highs': list(self.kline_highs)[-20:],
                'lows': list(self.kline_lows)[-20:],
                'volumes': list(self.volumes)[-20:],
                'timestamp': now
            }
            self.highest_price = price
            self.highest_time = now
            if self.lowest_price == 0:
                self.lowest_price = price
                self.lowest_time = now

            self._save_position_to_db()

            record_trade(
                user_id=self.user_id,
                key_id=self.key_id,
                bot_mode="expert",
                sub_mode="ai",
                symbol=self.symbol,
                side="buy",
                price=price,
                quantity=actual_bought,
                amount_usdt=buy_amount,
                fee=buy_fee,
                order_id=order_id,
                market_state=self.market_analyzer.get_state_string(),
                is_manual=False
            )

            # 通知策略切换器
            self.strategy_switcher.update_after_trade({
                "side": "buy",
                "price": price,
                "quantity": actual_bought
            })

            self._reset_trade_fail()
            if self.callback:
                self.callback(self.key_id, self.symbol, "买入", price, now)
            self._log("系统", f"{self.symbol} 买入 @ {price:.6f}")
            self._log("系统", f"{self.symbol} 买入 {buy_amount:.2f} USDT, 数量 {actual_bought:.6f}", price)
            self._set_action("buy", f"买入成功 order_id={order_id}")
            return True

        except Exception as e:
            err_str = str(e)
            if "10029" in err_str or "not whitelisted" in err_str.lower():
                self.buy_disabled = True
                self._log("系统", f"{self.symbol} 买入永久禁用：API权限不足。错误: {e}")
                self._set_action("blocked", f"白名单/权限限制: {e}")
            else:
                self._log("系统", f"{self.symbol} 买入失败: {e}")
                self._record_trade_fail(str(e))
            return False

    # ========== 补仓逻辑（保持不变，但增加策略判断） ==========
    def _should_add_position(self, price: float, atr: float, usdt_balance: float) -> bool:
        if time.time() < self._add_fail_until:
            self._set_action("hold", "补仓失败冷却中")
            return False
        if not self.position["has_position"]:
            self._set_action("hold", "无持仓，不补仓")
            return False
        if not self._has_tradable_position(price):
            self._set_action("hold", "当前仅残仓，不进入补仓")
            return False
        if self._in_trade_cooldown():
            self._set_action("hold", "交易失败冷却中，不补仓")
            return False
        if not self.risk_manager.can_add_position(self.symbol):
            self._set_action("hold", "风险管理禁止补仓")
            return False

        avg_price = self.position["avg_price"]
        if avg_price == 0:
            self._set_action("hold", "成本价为0，不补仓")
            return False

        market_trend = self.timeframe_analyzer.get_higher_trend(self.symbol)
        if market_trend == 'bear':
            self._set_action("hold", "大周期空头，不补仓")
            return False

        # 根据市场状态决定是否补仓
        market_state = self.strategy_switcher.current_state
        if market_state == "ranging":
            # 震荡市场：网格策略的补仓由网格逻辑处理，此处不重复
            self._set_action("hold", "震荡市场由网格策略管理，跳过常规补仓")
            return False

        health = self.risk_manager.get_health_score(self.symbol)
        if health < 30:
            self._set_action("hold", f"健康度过低 {health:.1f}")
            return False

        loss_pct = (avg_price - price) / avg_price
        if loss_pct <= 0:
            self._set_action("hold", "当前非浮亏，不补仓")
            return False
        min_loss_pct = 0.005
        if loss_pct < min_loss_pct:
            self._set_action("hold", f"浮亏不足 {loss_pct * 100:.2f}%")
            return False

        loss_atr = (avg_price - price) / atr if atr != 0 else 0
        if loss_atr >= 0.5 or loss_pct >= 0.03:
            initial_qty = self.position["qty"]
            ratios = self.risk_manager.get_param("add_position_ratios", self.symbol, [0.5, 0.3, 0.2])
            add_qty = self.add_position_logic.calculate_add_qty(initial_qty, self.add_count, ratios)
            if add_qty > 0:
                est_amount = add_qty * price
                if est_amount > usdt_balance:
                    self._set_action("hold", f"USDT余额不足补仓 {est_amount:.2f} > {usdt_balance:.2f}")
                    self._add_fail_until = time.time() + 60
                    return False
            self._set_action("scale", f"补仓条件满足 loss_pct={loss_pct * 100:.2f}%, loss_atr={loss_atr:.2f}")
            return True

        self._set_action("hold", "补仓条件未满足")
        return False

    def _execute_add_position(self, usdt_balance: float, price: float, now: float) -> bool:
        avg_price = self.position["avg_price"]
        if avg_price == 0:
            self._set_action("hold", "成本价为0，无法补仓")
            return False
        initial_qty = self.position["qty"]
        ratios = self.risk_manager.get_param("add_position_ratios", self.symbol, [0.5, 0.3, 0.2])
        add_qty = self.add_position_logic.calculate_add_qty(initial_qty, self.add_count, ratios)
        if add_qty <= 0:
            self._set_action("hold", "补仓计算数量<=0")
            return False
        add_amount = add_qty * price
        if add_amount < self.min_order_value:
            add_amount = self.min_order_value
        if self.max_add_amount is not None:
            add_amount = min(add_amount, self.max_add_amount)
        if add_amount > usdt_balance:
            self._set_action("hold", f"USDT余额不足补仓 {add_amount:.2f} > {usdt_balance:.2f}")
            self._add_fail_until = time.time() + 60
            return False
        try:
            order_id = self.market_buy(add_amount)
            if order_id is None:
                self._record_trade_fail("补仓下单返回空order_id")
                self._add_fail_until = time.time() + 60
                return False
            time.sleep(2)
            new_balances = self.get_balances()
            new_base = new_balances[1]
            old_qty = self.position["qty"]
            if new_base <= old_qty:
                self._record_trade_fail("补仓后持仓未增加")
                self._add_fail_until = time.time() + 60
                return False
            actual_added = new_base - old_qty
            if actual_added <= 0:
                self._record_trade_fail("补仓实际成交数量<=0")
                self._add_fail_until = time.time() + 60
                return False
            add_fee = add_amount * self.slippage
            total_cost = add_amount + add_fee
            with self._position_lock:
                old_cost = self.position["avg_price"] * old_qty
                new_total_cost = old_cost + total_cost
                total_qty = new_base
                if total_qty != 0:
                    self.position["avg_price"] = new_total_cost / total_qty
                self.position["qty"] = new_base
                self.position["last_trade_time"] = now
                self.add_count += 1
                self.last_add_price = price
            self.add_records.append({
                'price': price,
                'amount': add_amount,
                'quantity': actual_added,
                'timestamp': now
            })
            self._save_position_to_db()
            record_trade(
                user_id=self.user_id,
                key_id=self.key_id,
                bot_mode="expert",
                sub_mode="ai",
                symbol=self.symbol,
                side="buy",
                price=price,
                quantity=actual_added,
                amount_usdt=add_amount,
                fee=add_fee,
                order_id=order_id,
                market_state=self.market_analyzer.get_state_string(),
                is_manual=False
            )
            self._reset_trade_fail()
            if self.callback:
                self.callback(self.key_id, self.symbol, "补仓", price, now)
            self._log("系统", f"{self.symbol} 补仓 @ {price:.6f}")
            self._log("系统", f"{self.symbol} 补仓 {add_amount:.2f} USDT, 数量 {actual_added:.6f}", price)
            self._set_action("scale", f"补仓成功 order_id={order_id}")
            return True
        except Exception as e:
            self._log("系统", f"{self.symbol} 补仓失败: {e}")
            self._record_trade_fail(str(e))
            self._add_fail_until = time.time() + 60
            return False

    # ========== 卖出逻辑（融合策略切换） ==========
    def _should_sell(self, price: float, atr_price: float, rsi: float, volume_ratio: float,
                     market_trend: str, hold_hours: float, usdt_balance: float = None) -> Tuple[bool, List[Tuple[float, float]]]:
        if not self.position["has_position"]:
            self._set_action("hold", "无持仓，不卖出")
            return False, []

        avg_price = self.position["avg_price"]
        if avg_price == 0:
            self._set_action("hold", "成本价为0，不卖出")
            return False, []

        current_qty = self.position["qty"]
        position_value = current_qty * price

        # 残仓处理
        if usdt_balance is not None and usdt_balance < self.min_order_value and position_value >= self.min_order_value:
            self._set_action("sell", f"USDT余额不足 {usdt_balance:.2f}，强制卖出全部持仓")
            return True, [(current_qty, price)]

        if 0 < position_value < self.min_order_value:
            hold_seconds = time.time() - self.position.get("entry_time", time.time())
            if hold_seconds > 1800:
                self._set_action("sell", f"残仓强制清仓（持有{hold_seconds / 60:.0f}分钟）")
                return True, [(current_qty, price)]
            else:
                self._set_action("hold", f"残仓观察 {position_value:.2f}U < {self.min_order_value:.2f}U")
                return False, []

        # 使用策略切换器获取卖出信号
        data = {
            "current_price": price,
            "current_qty": current_qty,
            "avg_price": avg_price,
            "prices": list(self.kline_prices),
            "volumes": list(self.volumes),
            "highs": list(self.kline_highs),
            "lows": list(self.kline_lows)
        }
        should_sell_strategy, suggested_ratio = self.strategy_switcher.get_sell_signal(data)

        if should_sell_strategy:
            # 计算卖出数量
            sell_qty = current_qty * suggested_ratio
            sell_qty = min(sell_qty, current_qty)

            # 如果建议全部卖出，使用全仓
            if suggested_ratio >= 0.99:
                sell_orders = [(current_qty, price)]
            else:
                # 分仓卖出，基于exit_strategy
                sell_orders = self.exit_strategy.calculate_sell_orders(
                    current_qty, price, avg_price, atr_price, rsi, volume_ratio, market_trend, hold_hours
                )
                if not sell_orders:
                    sell_orders = [(sell_qty, price)]

            self._set_action("sell", f"策略信号卖出, 市场状态={self.strategy_switcher.current_state}, 建议比例={suggested_ratio:.2f}")
            return True, sell_orders

        # 原有退出策略作为后备
        sell_orders = self.exit_strategy.calculate_sell_orders(
            current_qty, price, avg_price, atr_price, rsi, volume_ratio, market_trend, hold_hours
        )
        if sell_orders:
            self._set_action("sell", f"卖出条件满足，计划单数={len(sell_orders)}")
            return True, sell_orders

        self._set_action("hold", "卖出条件未满足")
        return False, []

    def _execute_sell(self, sell_orders: List[Tuple[float, float]], now: float) -> bool:
        if not sell_orders:
            self._set_action("hold", "无卖单计划")
            return False
        if self._in_trade_cooldown():
            self._set_action("hold", "交易失败冷却中，不卖出")
            return False
        if time.time() < self._sell_fail_until:
            self._set_action("hold", "卖出失败冷却中")
            return False

        price = self.get_current_price()
        if price is None:
            self._set_action("hold", "当前价格为空，不卖出")
            return False
        self.sync_position_from_balance()
        with self._position_lock:
            current_qty = self.position["qty"]
            avg_price = self.position["avg_price"]
        if current_qty <= 0:
            self._log("系统", f"{self.symbol} 无持仓，跳过卖出")
            self._set_action("hold", "无持仓，跳过卖出")
            return False

        total_qty = sum(qty for qty, _ in sell_orders)
        if total_qty <= 0:
            self._set_action("hold", "卖出计划数量<=0")
            return False
        planned_qty = min(total_qty, current_qty)
        min_order = self.config.get("min_order_value", 5.0)
        planned_value = planned_qty * price
        full_value = current_qty * price

        if planned_value < min_order <= full_value:
            self._log("系统", f"{self.symbol} 计划卖出价值 {planned_value:.2f}U 小于最小额，改为整仓卖出")
            planned_qty = current_qty
            planned_value = full_value

        if planned_value < min_order:
            self._log("系统", f"{self.symbol} 卖出总价值 {planned_value:.2f} USDT 小于最小订单额 {min_order}，跳过卖出")
            self._sell_fail_count += 1
            if self._sell_fail_count >= self.MAX_SELL_FAIL:
                self._sell_fail_until = time.time() + self.SELL_FAIL_COOLDOWN
                self._log("系统", f"连续卖出失败{self.MAX_SELL_FAIL}次，进入冷却{self.SELL_FAIL_COOLDOWN}秒")
                self._sell_fail_count = 0
            self._set_action("hold", f"卖出价值不足 {planned_value:.2f} < {min_order:.2f}")
            return False

        raw_qty = math.floor(planned_qty / self.step) * self.step
        if raw_qty <= 0:
            self._log("系统", f"{self.symbol} 计算出的可卖数量为0，跳过卖出")
            self._set_action("hold", "步长裁剪后卖出数量为0")
            return False

        try:
            order_id = self.market_sell(raw_qty)
            if order_id is None:
                self._record_trade_fail("卖出下单返回空order_id")
                self._sell_fail_count += 1
                if self._sell_fail_count >= self.MAX_SELL_FAIL:
                    self._sell_fail_until = time.time() + self.SELL_FAIL_COOLDOWN
                    self._sell_fail_count = 0
                return False

            sold_value = raw_qty * price
            sell_fee = sold_value * self.slippage
            cost = avg_price * raw_qty
            pnl = sold_value - cost - sell_fee
            hold_seconds = int(now - self.entry_time) if self.entry_time else 0
            exit_reason = "take_profit"
            exit_kline_snapshot = {
                'prices': list(self.kline_prices)[-20:],
                'highs': list(self.kline_highs)[-20:],
                'lows': list(self.kline_lows)[-20:],
                'volumes': list(self.volumes)[-20:],
                'timestamp': now
            }
            record_trade(
                user_id=self.user_id,
                key_id=self.key_id,
                bot_mode="expert",
                sub_mode="ai",
                symbol=self.symbol,
                side="sell",
                price=price,
                quantity=raw_qty,
                amount_usdt=sold_value,
                fee=sell_fee,
                order_id=order_id,
                pnl=pnl,
                exit_reason=exit_reason,
                hold_seconds=hold_seconds,
                entry_score=self._calculate_buy_score(),
                market_state=self.market_analyzer.get_state_string(),
                entry_kline=self.entry_kline_snapshot,
                exit_kline=exit_kline_snapshot,
                highest_price=self.highest_price,
                highest_time=datetime.fromtimestamp(self.highest_time) if self.highest_time else None,
                lowest_price=self.lowest_price,
                lowest_time=datetime.fromtimestamp(self.lowest_time) if self.lowest_time else None,
                add_records=self.add_records,
                is_manual=False
            )
            self._after_sell(
                pnl=pnl,
                exit_reason=exit_reason,
                hold_seconds=hold_seconds,
                market_state=self.market_analyzer.get_state_string(),
                entry_score=self._calculate_buy_score(),
                add_records=self.add_records,
                price=price,
                quantity=raw_qty
            )
            with self._position_lock:
                self.position["qty"] -= raw_qty
                if self.position["qty"] <= 0:
                    self.position["has_position"] = False
                    self.position["qty"] = 0.0
                    self.position["avg_price"] = 0.0
                    self.add_count = 0
                    self._clear_position_in_db()
                    self.entry_kline_snapshot = None
                    self.highest_price = 0.0
                    self.highest_time = 0
                    self.lowest_price = 0.0
                    self.lowest_time = 0
                    self.add_records = []
                else:
                    self.position["has_position"] = True
                    self._save_position_to_db()

            # 通知策略切换器
            self.strategy_switcher.update_after_trade({
                "side": "sell",
                "price": price,
                "quantity": raw_qty
            })

            if avg_price != 0:
                is_win = pnl > 0
                self.risk_manager.update_health(self.symbol, pnl, is_win)
                if not is_win:
                    self.consecutive_losses += 1
                    if self.consecutive_losses >= 3:
                        self.buy_blocked_until = now + 300
                        self._log("系统", f"{self.symbol} 连续亏损3次，暂停买入5分钟")
                else:
                    self.consecutive_losses = 0

            self._reset_trade_fail()
            self._sell_fail_count = 0
            if self.callback:
                self.callback(self.key_id, self.symbol, "卖出", price, now)
            self._log("系统", f"{self.symbol} 卖出 @ {price:.6f}")
            self._log("系统", f"{self.symbol} 卖出 {raw_qty:.6f}, 净盈亏: {pnl:.2f} USDT", price)
            self._set_action("sell", f"卖出成功 order_id={order_id}, qty={raw_qty:.6f}")
            return True
        except Exception as e:
            self._log("系统", f"{self.symbol} 卖出失败: {e}")
            self._record_trade_fail(str(e))
            self._sell_fail_count += 1
            if self._sell_fail_count >= self.MAX_SELL_FAIL:
                self._sell_fail_until = time.time() + self.SELL_FAIL_COOLDOWN
                self._sell_fail_count = 0
            return False

    def _process_tick(self, price: float, now: float):
        self.sync_position_from_balance()
        self.update_kline(price, now)
        self._update_timeframe_klines()

        # 更新市场状态分类
        if len(self.kline_prices) >= 30:
            self.strategy_switcher.update_market_state(
                list(self.kline_highs)[-50:],
                list(self.kline_lows)[-50:],
                list(self.kline_prices)[-50:]
            )
            self.strategy_switcher.select_strategy()

        if len(self.kline_prices) < 50:
            return

        usdt, base_balance = self.get_balances()
        with self._position_lock:
            if self.position["has_position"] and price > self.position["highest_price"]:
                self.position["highest_price"] = price
            if self.position["has_position"] and price > self.highest_price_since_entry:
                self.highest_price_since_entry = price
        if self.position["has_position"]:
            if price > self.highest_price:
                self.highest_price = price
                self.highest_time = now
            if price < self.lowest_price or self.lowest_price == 0:
                self.lowest_price = price
                self.lowest_time = now

        atr_price = self._calculate_atr()
        rsi = self.indicators.rsi(list(self.kline_prices), 14) or 50
        volume_ratio = 1.0
        if len(self.volumes) >= 20:
            avg_vol = sum(list(self.volumes)[-20:]) / 20
            if avg_vol > 0:
                volume_ratio = self.volumes[-1] / avg_vol
        market_trend = self.timeframe_analyzer.get_higher_trend(self.symbol)
        hold_hours = (now - self.entry_time) / 3600 if self.entry_time else 0

        tradable_position = self._has_tradable_position(price)
        dust_position = self._has_dust_position(price)

        # ========== 核心状态机 ==========
        if tradable_position:
            should_sell, sell_orders = self._should_sell(price, atr_price, rsi, volume_ratio, market_trend, hold_hours, usdt)
            if should_sell:
                if self._execute_sell(sell_orders, now):
                    return

        if tradable_position and time.time() >= self._add_fail_until:
            if self._should_add_position(price, atr_price, usdt):
                if self._execute_add_position(usdt, price, now):
                    return

        if dust_position:
            self._set_action("hold", f"残仓观察 {self._position_value(price):.2f}U，小于最小交易额，不卖不补")

        if not self.position["has_position"] and time.time() >= self._sell_fail_until:
            if self._should_buy(usdt, price):
                self._execute_buy(usdt, price, now)

        # 心跳和状态日志
        if now - self.last_heartbeat >= 20:
            self.last_heartbeat = now
            key_name = self._get_key_name()
            self._log("系统", f"{key_name} {self.symbol} AI模式心跳检查, 市场状态={self.strategy_switcher.current_state}")

        if now - self.last_status_log >= 300:
            self.last_status_log = now
            health = self.risk_manager.get_health_score(self.symbol)
            if self.position["has_position"] and self.position["avg_price"]:
                unrealized_pnl = (price - self.position["avg_price"]) * self.position["qty"]
                self._log("系统", f"{self.symbol} 状态: 持仓={self.position['qty']:.4f}, 持仓价值={self._position_value(price):.2f} USDT, 成本={self.position['avg_price']:.6f}, 浮动盈亏={unrealized_pnl:.2f} USDT, 健康度={health:.1f}, 市场状态={self.strategy_switcher.current_state}, 最终动作={self.last_action}, 原因={self.last_action_reason}", price)
            else:
                self._log("系统", f"{self.symbol} 状态: 无持仓, 健康度={health:.1f}, 市场状态={self.strategy_switcher.current_state}, 最终动作={self.last_action}, 原因={self.last_action_reason}", price)

        if self.callback:
            self.callback(self.key_id, self.symbol, "更新UI", price, now)

    def _run_loop(self):
        pass