# 文件路径: services/trade_service.py
from dao.trade_dao import TradeDAO
from dao.bot_session_dao import BotSessionDAO
from dao.coin_stats_dao import CoinStatsDAO
from dao.error_stats_dao import ErrorStatsDAO
from models.trade import Trade
from models.bot_session import BotSession
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def _classify_error(exit_reason: str, market_state: str, pnl: float, hold_seconds: int) -> str:
    if pnl >= 0:
        return None
    if exit_reason == 'stop_loss':
        return 'stop_loss_hit'
    elif exit_reason == 'take_profit' and market_state == 'trend':
        return 'take_profit_too_early'
    elif exit_reason == 'take_profit' and market_state == 'range':
        return None
    elif exit_reason == 'trailing_stop':
        return 'trailing_stop_hit'
    elif exit_reason == 'timeout':
        return 'hold_timeout_loss'
    elif exit_reason == 'force_clear':
        return 'force_clear_loss'
    else:
        return 'unknown_loss'

def record_trade(user_id, key_id, bot_mode, sub_mode, symbol, side, price, quantity, amount_usdt, fee, order_id,
                 pnl=None, exit_reason=None, hold_seconds=None, entry_score=None, market_state=None,
                 entry_kline=None, exit_kline=None, highest_price=None, highest_time=None,
                 lowest_price=None, lowest_time=None, add_records=None, platform=None, key_name=None,
                 is_manual=False, source_trade_id=None, trade_time=None):
    """
    trade_time: 交易实际发生的时间（datetime 对象），如果不传则使用当前时间
    """
    try:
        if order_id:
            existing = TradeDAO.get_by_order_id(order_id)
            if existing:
                logger.warning(f"交易记录已存在，order_id={order_id}")
                return
        if trade_time is None:
            trade_time = datetime.now()
        trade = Trade(
            user_id=user_id,
            key_id=key_id,
            platform=platform,
            key_name=key_name,
            bot_mode=bot_mode,
            sub_mode=sub_mode,
            symbol=symbol,
            side=side,
            price=price,
            quantity=quantity,
            amount_usdt=amount_usdt,
            fee=fee,
            order_id=order_id,
            source_trade_id=source_trade_id,
            is_manual=is_manual,
            timestamp=trade_time,           # 交易时间
            recorded_at=datetime.now(),     # 插入时间
            pnl=pnl,
            exit_reason=exit_reason,
            hold_seconds=hold_seconds,
            entry_score=entry_score,
            market_state=market_state,
            entry_kline=entry_kline,
            exit_kline=exit_kline,
            highest_price=highest_price,
            highest_time=highest_time,
            lowest_price=lowest_price,
            lowest_time=lowest_time,
            add_records=add_records
        )
        TradeDAO.create(trade)
    except Exception as e:
        logger.error(f"记录交易失败: {e}")
        return

    if side == 'sell' and pnl is not None:
        try:
            CoinStatsDAO.update_stats(key_id, symbol, pnl)
            if pnl < 0:
                error_type = _classify_error(exit_reason, market_state, pnl, hold_seconds)
                if error_type:
                    ErrorStatsDAO.increment_error(key_id, symbol, error_type, abs(pnl))
        except Exception as e:
            logger.error(f"更新统计失败: {e}")

def start_bot_session(user_id, key_id, symbol, bot_mode, sub_mode, config, initial_balance):
    session = BotSession(
        user_id=user_id,
        key_id=key_id,
        symbol=symbol,
        bot_mode=bot_mode,
        sub_mode=sub_mode,
        config=config,
        initial_balance=initial_balance,
        start_time=datetime.now(),
        status='running'
    )
    return BotSessionDAO.create(session)

def end_bot_session(session_id, final_balance):
    session = BotSessionDAO.get_by_id(session_id)
    if session:
        session.end_time = datetime.now()
        session.final_balance = final_balance
        session.pnl = final_balance - session.initial_balance
        session.pnl_percent = (session.pnl / session.initial_balance * 100) if session.initial_balance else 0
        session.status = 'stopped'
        BotSessionDAO.update(session)