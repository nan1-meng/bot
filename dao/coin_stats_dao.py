# 文件路径: dao/coin_stats_dao.py
from models.coin_stats import CoinStats
from utils.db import Session

class CoinStatsDAO:
    @staticmethod
    def update_stats(key_id: int, symbol: str, pnl: float):
        session = Session()
        try:
            record = session.query(CoinStats).filter_by(key_id=key_id, symbol=symbol).first()
            if not record:
                record = CoinStats(
                    key_id=key_id,
                    symbol=symbol,
                    total_trades=0,
                    win_trades=0,
                    total_profit=0.0,
                    total_loss=0.0,
                    avg_win=0.0,
                    avg_loss=0.0,
                    win_rate=0.0,
                    profit_factor=0.0,
                )
                session.add(record)

            total_trades = record.total_trades or 0
            win_trades = record.win_trades or 0
            total_profit = record.total_profit or 0.0
            total_loss = record.total_loss or 0.0
            pnl = pnl or 0.0

            total_trades += 1
            if pnl > 0:
                win_trades += 1
                total_profit += pnl
            else:
                total_loss += abs(pnl)

            loss_trades = total_trades - win_trades
            record.total_trades = total_trades
            record.win_trades = win_trades
            record.total_profit = total_profit
            record.total_loss = total_loss
            record.avg_win = (total_profit / win_trades) if win_trades > 0 else 0.0
            record.avg_loss = (total_loss / loss_trades) if loss_trades > 0 else 0.0
            record.win_rate = (win_trades / total_trades * 100.0) if total_trades > 0 else 0.0
            record.profit_factor = (total_profit / total_loss) if total_loss > 0 else 0.0
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
