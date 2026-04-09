# ============================================================
# 文件: strategies/strategy_switcher.py
# 说明: 根据市场状态自动切换交易策略
# ============================================================

from typing import Dict, Any, Optional, Tuple, List
from strategies.grid_strategy import GridStrategy
from strategies.momentum_strategy import MomentumStrategy
from core.market_classifier import MarketClassifier


class StrategySwitcher:
    """策略切换器，管理多种策略并根据市场状态激活最佳策略"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.grid_strategy = GridStrategy(config.get("grid", {}))
        self.momentum_strategy = MomentumStrategy(config.get("momentum", {}))
        self.market_classifier = MarketClassifier()
        self.current_state = "unknown"
        self.active_strategy = "momentum"  # 默认动量策略

    def update_market_state(self, highs: List[float], lows: List[float], closes: List[float]) -> str:
        """更新市场状态并返回"""
        result = self.market_classifier.classify(highs, lows, closes)
        self.current_state = result["state"]
        return self.current_state

    def select_strategy(self) -> str:
        """根据当前市场状态选择策略"""
        if self.current_state == "trending":
            self.active_strategy = "momentum"
        elif self.current_state == "ranging":
            self.active_strategy = "grid"
        elif self.current_state == "high_volatility":
            # 高波动时使用动量策略但降低仓位
            self.active_strategy = "momentum"
        else:
            self.active_strategy = "momentum"
        return self.active_strategy

    def get_buy_signal(self, data: Dict[str, Any]) -> Tuple[bool, float]:
        """
        获取买入信号及建议仓位比例
        返回: (是否买入, 建议仓位比例0~1)
        """
        if self.active_strategy == "grid":
            return self.grid_strategy.should_buy(data)
        else:
            return self.momentum_strategy.should_buy(data)

    def get_sell_signal(self, data: Dict[str, Any]) -> Tuple[bool, float]:
        """
        获取卖出信号及建议卖出比例
        返回: (是否卖出, 建议卖出比例0~1)
        """
        if self.active_strategy == "grid":
            return self.grid_strategy.should_sell(data)
        else:
            return self.momentum_strategy.should_sell(data)

    def get_grid_levels(self, current_price: float) -> Optional[Dict]:
        """获取网格策略的网格层级"""
        if self.active_strategy == "grid":
            return self.grid_strategy.get_grid_levels(current_price)
        return None

    def update_after_trade(self, trade_info: Dict):
        """交易后更新策略内部状态"""
        if self.active_strategy == "grid":
            self.grid_strategy.update_after_trade(trade_info)
        else:
            self.momentum_strategy.update_after_trade(trade_info)