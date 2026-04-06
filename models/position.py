# models/position.py
from dao.trade_dao import TradeDAO

class Position:
    def __init__(self, symbol):
        self.symbol = symbol
        self.quantity = 0.0
        self.avg_cost = 0.0
        self.realized_pnl = 0.0

    def update_from_trade(self, trade):
        """
        使用历史交易更新持仓
        """
        total_cost = self.avg_cost * self.quantity + trade.price * trade.quantity
        self.quantity += trade.quantity
        if self.quantity > 0:
            self.avg_cost = total_cost / self.quantity

    def floating_pnl(self, current_price=None):
        """
        计算浮动盈亏
        """
        if self.quantity <= 0:
            return 0.0
        if current_price is None:
            current_price = self.get_market_price()
        return (current_price - self.avg_cost) * self.quantity

    def has_tradable_quantity(self, min_value=0.0):
        """
        判断持仓是否大于最小交易额可交易
        """
        return self.quantity > 0.0 and self.floating_pnl() >= min_value

    def get_market_price(self):
        """
        获取当前市场价格，支持接口扩展
        """
        return 1.0  # 占位，可接行情接口