# 文件路径: services/reconciliation_service.py
from dao.trade_dao import TradeDAO
from services.trade_recorder import record_trade

class ReconciliationService:
    def __init__(self, key_service):
        self.key_service = key_service
    def reconcile_symbol(self, user_id, key_id, platform, symbol, account_position_qty, fetch_recent_trades):
        trades = fetch_recent_trades(symbol, 0) or []
        inserted = 0
        for t in trades:
            order_id = str(t.get('source_trade_id') or t.get('order_id') or '')
            if order_id and TradeDAO.get_by_order_id(order_id):
                continue
            record_trade(
                user_id=user_id, key_id=key_id, platform=platform,
                bot_mode='manual_sync', sub_mode='', symbol=symbol, side=t.get('side','buy'),
                price=float(t.get('price') or 0), quantity=float(t.get('amount') or 0), amount_usdt=float(t.get('amount_usdt') or ((t.get('price') or 0)*(t.get('amount') or 0))),
                fee=float(t.get('fee') or 0), order_id=order_id, is_manual=True, source_trade_id=order_id
            )
            inserted += 1
        return {'inserted': inserted, 'remote_qty': account_position_qty}
