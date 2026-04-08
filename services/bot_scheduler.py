# 文件路径: services/bot_scheduler.py
import threading
import time
from typing import Dict, List, Any, Callable
import logging

logger = logging.getLogger(__name__)

class BotScheduler(threading.Thread):
    """统一调度器：每种机器人模式一个实例，批量获取价格后逐个决策"""
    def __init__(self, key_service, mode: str, action_callback: Callable):
        super().__init__(daemon=True)
        self.key_service = key_service
        self.mode = mode
        self.action_callback = action_callback
        self.bots: Dict[int, Dict[str, Any]] = {}  # {key_id: {symbol: bot_instance}}
        self._lock = threading.RLock()
        self.running = True
        self.interval = 2  # 秒

    def register_bot(self, key_id: int, symbol: str, bot_instance):
        with self._lock:
            if key_id not in self.bots:
                self.bots[key_id] = {}
            self.bots[key_id][symbol] = bot_instance
            logger.info(f"注册机器人 {self.mode}/{symbol} 到调度器")

    def unregister_bot(self, key_id: int, symbol: str):
        with self._lock:
            if key_id in self.bots and symbol in self.bots[key_id]:
                del self.bots[key_id][symbol]
                if not self.bots[key_id]:
                    del self.bots[key_id]
                logger.info(f"注销机器人 {self.mode}/{symbol}")

    def run(self):
        logger.info(f"调度器 {self.mode} 启动")
        while self.running:
            start = time.time()
            try:
                self._tick()
            except Exception as e:
                logger.error(f"调度器 {self.mode} 异常: {e}")
            elapsed = time.time() - start
            sleep_time = max(0.1, self.interval - elapsed)
            time.sleep(sleep_time)

    def _tick(self):
        # 收集所有需要处理的币种
        with self._lock:
            bots_copy = {k: v.copy() for k, v in self.bots.items()}
        if not bots_copy:
            return

        # 按 Key 分组，批量获取价格
        for key_id, symbols_dict in bots_copy.items():
            key = self.key_service.get_key(key_id)
            if not key:
                continue
            client = self.key_service.get_client(key_id)
            if not client:
                continue
            # 批量获取这些币种的最新价格（逐个调用，无法批量，但可以复用连接）
            prices = {}
            for symbol in symbols_dict.keys():
                try:
                    price = client.get_ticker(symbol)
                    if price:
                        prices[symbol] = price
                except Exception as e:
                    logger.debug(f"获取 {symbol} 价格失败: {e}")
            # 逐个机器人决策
            for symbol, bot in symbols_dict.items():
                if not bot.running:
                    continue
                price = prices.get(symbol)
                if price is None:
                    continue
                try:
                    # 调用机器人的外部驱动方法
                    bot.on_tick(price, time.time())
                except Exception as e:
                    logger.error(f"机器人 {symbol} 决策异常: {e}")

    def stop(self):
        self.running = False