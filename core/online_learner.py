# ============================================================
# 文件: core/online_learner.py
# 说明: 在线学习器，自动分析亏损交易并调整风险参数
# ============================================================

import threading
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from utils.db import Session
from dao.trade_dao import TradeDAO
from dao.strategy_params_dao import StrategyParamsDAO
from dao.symbol_config_dao import SymbolConfigDAO
from models.trade import Trade
from core.learning_reporter import LearningReporter
import logging

logger = logging.getLogger(__name__)


class OnlineLearner:
    def __init__(self, user_id: int, risk_manager, analysis_interval: int = 3600):
        self.user_id = user_id
        self.risk_manager = risk_manager
        self.analysis_interval = analysis_interval
        self.last_analysis = 0
        self.running = False
        self.thread = None
        self._stop_event = threading.Event()
        self.reporter = LearningReporter(user_id)
        logger.info(f"OnlineLearner 初始化完成，用户 {user_id}")

    def start(self):
        if self.running:
            return
        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        logger.info(f"在线学习器已启动 (user_id={self.user_id})")

    def stop(self):
        self.running = False
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
        logger.info(f"在线学习器已停止 (user_id={self.user_id})")

    def _loop(self):
        last_snapshot_time = 0
        while self.running and not self._stop_event.is_set():
            now = time.time()
            if now - self.last_analysis >= self.analysis_interval:
                self.last_analysis = now
                self.analyze_and_adjust()
            if now - last_snapshot_time >= 3600:
                last_snapshot_time = now
                self._record_strategy_snapshot()
            time.sleep(60)

    def on_trade_complete(self, trade_info: Dict):
        if trade_info.get('side') != 'sell':
            return
        pnl = trade_info.get('pnl')
        if pnl is None:
            return
        symbol = trade_info.get('symbol')
        logger.info(f"学习器收到交易完成: {symbol}, pnl={pnl:.2f}")
        if pnl >= 0:
            self.risk_manager.update_health(symbol, pnl, True)
            self.reporter.record_win(trade_info)
            return

        self.risk_manager.update_health(symbol, pnl, False)
        error_type = self._classify_error(trade_info)
        logger.info(f"亏损交易分析: {symbol}, 错误类型={error_type}, pnl={pnl:.2f}")
        self.reporter.record_loss(trade_info, error_type)
        self._adjust_parameters(trade_info, error_type)

    def _classify_error(self, trade: Dict) -> str:
        reason = trade.get('exit_reason', 'unknown')
        market_state = trade.get('market_state', 'unknown')
        if reason == 'stop_loss':
            return 'stop_loss_hit'
        elif reason == 'take_profit' and market_state == 'trend':
            return 'take_profit_too_early'
        elif reason == 'take_profit' and market_state == 'range':
            return None
        elif reason == 'trailing_stop':
            return 'trailing_stop_hit'
        elif reason == 'timeout':
            return 'hold_timeout_loss'
        else:
            return 'unknown_loss'

    def _adjust_parameters(self, trade: Dict, error_type: str):
        symbol = trade['symbol']
        pnl_abs = abs(trade['pnl'])
        logger.info(f"调整参数: {symbol}, 错误类型={error_type}, 亏损={pnl_abs:.2f}")

        if error_type == 'stop_loss_hit':
            current_mult = self.risk_manager.get_param("stop_loss_atr_mult", symbol, 1.5)
            new_mult = min(2.5, current_mult + 0.1)
            if new_mult != current_mult:
                self.risk_manager.set_param("stop_loss_atr_mult", new_mult, symbol)
                self.reporter.record_adjustment(
                    symbol, "stop_loss_atr_mult", current_mult, new_mult,
                    f"止损亏损 {pnl_abs:.2f} USDT，放宽止损倍数"
                )
                logger.info(f"调整 {symbol} stop_loss_atr_mult: {current_mult} -> {new_mult}")

        elif error_type == 'take_profit_too_early':
            current_tp = self.risk_manager.get_param("take_profit_atr_mult", symbol, 1.0)
            new_tp = min(2.0, current_tp + 0.1)
            if new_tp != current_tp:
                self.risk_manager.set_param("take_profit_atr_mult", new_tp, symbol)
                self.reporter.record_adjustment(
                    symbol, "take_profit_atr_mult", current_tp, new_tp,
                    f"过早止盈 {pnl_abs:.2f} USDT，提高止盈目标倍数"
                )
                logger.info(f"调整 {symbol} take_profit_atr_mult: {current_tp} -> {new_tp}")

        if trade.get('add_records') and len(trade['add_records']) > 0:
            current_max = self.risk_manager.get_param("add_position_max_times", symbol, 3)
            if current_max > 1:
                new_max = current_max - 1
                self.risk_manager.set_param("add_position_max_times", new_max, symbol)
                self.reporter.record_adjustment(
                    symbol, "add_position_max_times", current_max, new_max,
                    f"补仓后仍亏损 {pnl_abs:.2f} USDT，减少最大补仓次数"
                )
                logger.info(f"调整 {symbol} add_position_max_times: {current_max} -> {new_max}")
            current_ratios = self.risk_manager.get_param("add_position_ratios", symbol, [0.5, 0.3, 0.2])
            new_ratios = [max(0.05, r * 0.9) for r in current_ratios]
            if new_ratios != current_ratios:
                self.risk_manager.set_param("add_position_ratios", new_ratios, symbol)
                self.reporter.record_adjustment(
                    symbol, "add_position_ratios", current_ratios, new_ratios,
                    f"补仓后亏损，降低补仓比例"
                )
                logger.info(f"调整 {symbol} add_position_ratios: {current_ratios} -> {new_ratios}")

        recent_losses = self.reporter.get_recent_losses(symbol, limit=3)
        if len(recent_losses) >= 3:
            current_threshold = self.risk_manager.get_param("buy_threshold_base", symbol, 50)
            new_threshold = max(30, current_threshold - 5)
            if new_threshold != current_threshold:
                self.risk_manager.set_param("buy_threshold_base", new_threshold, symbol)
                self.reporter.record_adjustment(
                    symbol, "buy_threshold_base", current_threshold, new_threshold,
                    f"连续亏损3次，降低买入阈值"
                )
                logger.info(f"调整 {symbol} buy_threshold_base: {current_threshold} -> {new_threshold}")

        if pnl_abs > 5:
            current_pos_ratio = self.risk_manager.get_param("position_ratio_base", symbol, 0.5)
            new_pos_ratio = max(0.1, current_pos_ratio - 0.05)
            if new_pos_ratio != current_pos_ratio:
                self.risk_manager.set_param("position_ratio_base", new_pos_ratio, symbol)
                self.reporter.record_adjustment(
                    symbol, "position_ratio_base", current_pos_ratio, new_pos_ratio,
                    f"亏损较大 ({pnl_abs:.2f} USDT)，降低仓位比例"
                )
                logger.info(f"调整 {symbol} position_ratio_base: {current_pos_ratio} -> {new_pos_ratio}")

    def analyze_and_adjust(self):
        logger.info(f"开始每小时学习分析，用户 {self.user_id}")
        session = Session()
        try:
            cutoff = datetime.now() - timedelta(days=7)
            trades = session.query(Trade).filter(
                Trade.user_id == self.user_id,
                Trade.side == 'sell',
                Trade.executed_at >= cutoff,
                Trade.is_manual == False
            ).all()
            if not trades:
                logger.info(f"用户 {self.user_id} 无近期机器人交易，跳过学习")
                return

            total_trades = len(trades)
            losing_trades = [t for t in trades if t.pnl and t.pnl < 0]
            losing_count = len(losing_trades)
            win_rate = (total_trades - losing_count) / total_trades if total_trades else 0
            logger.info(f"近期交易统计: 总数={total_trades}, 亏损数={losing_count}, 胜率={win_rate:.2%}")

            error_stats = {}
            for t in losing_trades:
                error_type = t.exit_reason or 'unknown'
                error_stats[error_type] = error_stats.get(error_type, 0) + 1
            logger.info(f"错误类型统计: {error_stats}")

            stop_loss_ratio = error_stats.get('stop_loss', 0) / losing_count if losing_count else 0
            if stop_loss_ratio > 0.5:
                current_mult = self.risk_manager.get_param("stop_loss_atr_mult", default=1.5)
                new_mult = min(2.5, current_mult + 0.1)
                if new_mult != current_mult:
                    self.risk_manager.set_param("stop_loss_atr_mult", new_mult)
                    logger.info(f"止损亏损占比 {stop_loss_ratio:.1%}，放宽止损倍数至 {new_mult}")

            early_take_profit = error_stats.get('take_profit_too_early', 0) / losing_count if losing_count else 0
            if early_take_profit > 0.3:
                current_tp = self.risk_manager.get_param("take_profit_atr_mult", default=1.0)
                new_tp = min(2.0, current_tp + 0.1)
                if new_tp != current_tp:
                    self.risk_manager.set_param("take_profit_atr_mult", new_tp)
                    logger.info(f"过早止盈占比 {early_take_profit:.1%}，提高止盈目标倍数至 {new_tp}")

            if win_rate < 0.4 and total_trades >= 10:
                current_base = self.risk_manager.get_param("buy_threshold_base", default=50)
                new_base = max(30, current_base - 5)
                if new_base != current_base:
                    self.risk_manager.set_param("buy_threshold_base", new_base)
                    logger.info(f"胜率过低 ({win_rate:.1%})，降低买入阈值基准至 {new_base}")

            configs = SymbolConfigDAO.get_by_api_key(self.risk_manager.key_id)
            for cfg in configs:
                if cfg.symbol:
                    health = self.risk_manager.get_health_score(cfg.symbol)
                    if health < 20:
                        last_trade = session.query(Trade).filter(
                            Trade.user_id == self.user_id,
                            Trade.symbol == cfg.symbol,
                            Trade.side == 'sell'
                        ).order_by(Trade.executed_at.desc()).first()
                        if last_trade:
                            days_since = (datetime.now() - last_trade.executed_at).days
                        else:
                            days_since = 999
                        if days_since >= 3:
                            current_th = self.risk_manager.get_param("buy_threshold_base", cfg.symbol, 50)
                            new_th = max(20, current_th - 10)
                            if new_th != current_th:
                                self.risk_manager.set_param("buy_threshold_base", new_th, cfg.symbol)
                                logger.info(f"币种 {cfg.symbol} 健康度 {health} 且 {days_since} 天无交易，强制降低阈值至 {new_th}")

            # 写入汇总日志
            logger.info(f"在线学习分析完成，用户 {self.user_id}")
            try:
                from dao.system_log_dao import SystemLogDAO
                SystemLogDAO.add(
                    user_id=self.user_id,
                    key_id=self.risk_manager.key_id,
                    level="INFO",
                    category="学习",
                    message=f"在线学习完成: 分析交易{total_trades}笔, 胜率{win_rate:.1%}, 已调整参数"
                )
            except Exception as e:
                logger.error(f"写入系统日志失败: {e}")

        except Exception as e:
            logger.error(f"在线学习分析失败: {e}")
        finally:
            session.close()

    def _record_strategy_snapshot(self):
        if not self.risk_manager:
            return
        global_params = {}
        for param_name in ['stop_loss_atr_mult', 'take_profit_atr_mult', 'buy_threshold_base',
                           'position_ratio_base', 'add_position_max_times']:
            global_params[param_name] = self.risk_manager.get_param(param_name, default=None)
        self.reporter.record_snapshot(None, global_params)

        configs = SymbolConfigDAO.get_by_api_key(self.risk_manager.key_id)
        for cfg in configs:
            symbol = cfg.symbol
            if not symbol:
                continue
            params = {
                'health': self.risk_manager.get_health_score(symbol),
                'stop_loss_atr_mult': self.risk_manager.get_param('stop_loss_atr_mult', symbol, None),
                'take_profit_atr_mult': self.risk_manager.get_param('take_profit_atr_mult', symbol, None),
                'buy_threshold_base': self.risk_manager.get_param('buy_threshold_base', symbol, None),
                'add_position_ratios': self.risk_manager.get_param('add_position_ratios', symbol, None),
            }
            self.reporter.record_snapshot(symbol, params)