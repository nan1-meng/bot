# ============================================================
# 文件: core/ml_predictor.py
# 说明: 使用LightGBM预测未来N根K线涨跌概率
# ============================================================

import numpy as np
import pickle
import os
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from utils.db import Session
from models.trade import Trade
import logging

logger = logging.getLogger(__name__)

# 尝试导入lightgbm，若未安装则降级为模拟预测
try:
    import lightgbm as lgb
    LGB_AVAILABLE = True
except ImportError:
    LGB_AVAILABLE = False
    logger.warning("LightGBM未安装，将使用模拟预测器")


class MLPredictor:
    """机器学习预测器，使用LightGBM分类器预测涨跌"""

    def __init__(self, model_path: str = "ml_model.pkl"):
        self.model_path = model_path
        self.model = None
        self.feature_names = [
            'rsi', 'macd', 'macd_signal', 'bb_width', 'volume_ratio',
            'price_ma_ratio', 'volatility', 'trend_strength'
        ]
        self._load_or_create_model()

    def _load_or_create_model(self):
        """加载已有模型或创建新模型"""
        if not LGB_AVAILABLE:
            self.model = None
            return

        if os.path.exists(self.model_path):
            try:
                with open(self.model_path, 'rb') as f:
                    self.model = pickle.load(f)
                logger.info(f"已加载ML模型: {self.model_path}")
            except Exception as e:
                logger.error(f"加载模型失败: {e}")
                self._create_new_model()
        else:
            self._create_new_model()

    def _create_new_model(self):
        """创建新的LightGBM模型"""
        if not LGB_AVAILABLE:
            return
        params = {
            'objective': 'binary',
            'metric': 'binary_logloss',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'verbose': -1
        }
        self.model = lgb.LGBMClassifier(**params)
        logger.info("创建新的ML模型")

    def extract_features(self, prices: List[float], volumes: List[float],
                         highs: List[float], lows: List[float]) -> Optional[np.ndarray]:
        """从K线数据提取特征"""
        if len(prices) < 30:
            return None

        from core.indicators import Indicators
        ind = Indicators()

        # RSI
        rsi = ind.rsi(prices, 14) or 50.0

        # MACD
        macd, signal, hist = ind.macd(prices)
        macd = macd if macd is not None else 0.0
        signal = signal if signal is not None else 0.0

        # 布林带宽度
        upper, mid, lower = ind.bollinger_bands(prices, 20, 2)
        bb_width = (upper - lower) / mid if mid and mid > 0 else 0.0

        # 成交量比率
        avg_vol = np.mean(volumes[-20:]) if len(volumes) >= 20 else 1.0
        volume_ratio = volumes[-1] / avg_vol if avg_vol > 0 else 1.0

        # 价格与MA20比率
        ma20 = ind.sma(prices, 20)
        price_ma_ratio = prices[-1] / ma20 if ma20 and ma20 > 0 else 1.0

        # 波动率（ATR/价格）
        atr = self._calculate_atr(highs, lows, prices, 14)
        volatility = atr / prices[-1] if prices[-1] > 0 else 0.0

        # 趋势强度（ADX简化）
        trend_strength = self._calculate_trend_strength(prices)

        features = np.array([[
            rsi, macd, signal, bb_width, volume_ratio,
            price_ma_ratio, volatility, trend_strength
        ]])
        return features

    def _calculate_atr(self, highs, lows, closes, period=14):
        if len(highs) < period + 1:
            return 0.0
        tr_list = []
        for i in range(-period, 0):
            high = highs[i]
            low = lows[i]
            prev_close = closes[i-1]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)
        return np.mean(tr_list)

    def _calculate_trend_strength(self, prices):
        """简单的线性回归斜率作为趋势强度"""
        if len(prices) < 20:
            return 0.0
        y = np.array(prices[-20:])
        x = np.arange(20)
        slope = np.polyfit(x, y, 1)[0]
        return slope / np.mean(y) if np.mean(y) > 0 else 0.0

    def predict(self, features: np.ndarray) -> Tuple[float, float]:
        """
        返回(上涨概率, 下跌概率)
        """
        if not LGB_AVAILABLE or self.model is None or not hasattr(self.model, 'predict_proba'):
            # 模拟预测：基于RSI简单估计
            rsi = features[0][0]
            up_prob = max(0.3, min(0.7, (100 - rsi) / 100))
            return up_prob, 1.0 - up_prob

        try:
            proba = self.model.predict_proba(features)[0]
            # proba[0]是下跌概率，proba[1]是上涨概率
            return proba[1], proba[0]
        except Exception as e:
            logger.error(f"ML预测失败: {e}")
            return 0.5, 0.5

    def update_model(self, features: np.ndarray, label: int):
        """
        在线更新模型（增量学习）
        label: 1表示上涨，0表示下跌
        """
        if not LGB_AVAILABLE or self.model is None:
            return

        try:
            # LightGBM支持增量训练，使用partial_fit或重新训练
            # 这里简单起见，收集足够数据后定期重新训练
            # 实际生产可缓存数据定期重训
            pass
        except Exception as e:
            logger.error(f"模型更新失败: {e}")

    def save_model(self):
        """保存模型到文件"""
        if not LGB_AVAILABLE or self.model is None:
            return
        try:
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
            logger.info(f"模型已保存到 {self.model_path}")
        except Exception as e:
            logger.error(f"保存模型失败: {e}")

    def train_from_history(self, symbol: str, key_id: int):
        """从历史交易数据训练模型（离线训练）"""
        session = Session()
        try:
            trades = session.query(Trade).filter(
                Trade.key_id == key_id,
                Trade.symbol == symbol,
                Trade.side == 'sell',
                Trade.is_manual == False
            ).order_by(Trade.executed_at.asc()).all()

            if len(trades) < 50:
                logger.info(f"历史交易不足50笔，跳过训练")
                return

            # 构建训练数据（简化版，实际需要K线特征）
            X = []
            y = []
            for trade in trades:
                if trade.entry_kline and trade.exit_kline:
                    entry_prices = trade.entry_kline.get('prices', [])
                    if len(entry_prices) >= 30:
                        # 构造特征（简化，实际需完整K线）
                        features = self.extract_features(
                            entry_prices[-50:],
                            trade.entry_kline.get('volumes', [])[-50:],
                            trade.entry_kline.get('highs', [])[-50:],
                            trade.entry_kline.get('lows', [])[-50:]
                        )
                        if features is not None:
                            X.append(features[0])
                            label = 1 if trade.pnl > 0 else 0
                            y.append(label)

            if len(X) < 30:
                return

            X = np.array(X)
            y = np.array(y)

            self._create_new_model()
            self.model.fit(X, y)
            self.save_model()
            logger.info(f"模型训练完成，样本数: {len(X)}")
        except Exception as e:
            logger.error(f"模型训练失败: {e}")
        finally:
            session.close()