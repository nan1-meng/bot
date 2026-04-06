# 文件路径: services/portfolio_service.py
import sqlite3
from typing import Dict, Optional
from config import DATABASE_URI
from services.platform_service import PlatformService

class PortfolioService:
    def __init__(self, conn=None):
        self.platform_service = PlatformService()
    def get_fee_rate(self, platform: str) -> float:
        return self.platform_service.get_fee_rate(platform)
    def calc_unrealized_pnl(self, qty: float, avg_price: float, current_price: float, platform: str) -> float:
        if qty <= 0 or avg_price <= 0 or current_price <= 0:
            return 0.0
        fee_rate = self.get_fee_rate(platform)
        gross_sell = qty * current_price
        estimated_sell_fee = gross_sell * fee_rate
        estimated_cost_fee = qty * avg_price * fee_rate
        return (gross_sell - estimated_sell_fee) - (qty * avg_price + estimated_cost_fee)
