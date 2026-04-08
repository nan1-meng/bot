# 文件路径: services/key_service.py
import threading
import time
import math
from typing import Dict, Optional, Callable, Any
from datetime import datetime
from collections import deque
from dao.api_key_dao import ApiKeyDAO
from dao.symbol_config_dao import SymbolConfigDAO
from dao.trade_dao import TradeDAO
from models.trade import Trade
from utils.encryption import decrypt
from clients import create_client
from utils.db import Session
from utils.logger import get_logger
import logging

logger = get_logger(__name__)

class KeyService:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.keys: Dict[int, Dict] = {}
        self._lock = threading.RLock()
        self._global_services: Dict[int, Any] = {}
        self._online_learners: Dict[int, Any] = {}
        self._risk_managers: Dict[int, Any] = {}  # 新增：缓存每个 Key 的 RiskManager
        self._ws_managers: Dict[int, Any] = {}
        self._client_cache: Dict[int, Any] = {}

        self._monitor_running = False
        self._monitor_thread = None
        self._stop_monitor = threading.Event()
        self._balance_callbacks = []
        self._price_callbacks = []

        self._asset_update_running = True
        self._asset_update_thread = None
        self._current_selected_key = None

        self.load_from_db()
        self._start_asset_update_thread()
        self._start_schedulers()

    def _start_schedulers(self):
        from services.bot_scheduler import BotScheduler
        self.schedulers = {}
        for mode in ['expert', 'strategy', 'scalping', 'global_sell']:
            scheduler = BotScheduler(self, mode, self._on_bot_action)
            scheduler.start()
            self.schedulers[mode] = scheduler

    def _on_bot_action(self, key_id, symbol, action, price, msg):
        if self._balance_callbacks:
            for cb in self._balance_callbacks:
                try:
                    cb(key_id, None)
                except:
                    pass

    def load_from_db(self):
        db_keys = ApiKeyDAO.get_by_user(self.user_id)
        for db_key in db_keys:
            with self._lock:
                self.keys[db_key.id] = {
                    'platform': db_key.platform,
                    'api_key': decrypt(db_key.api_key),
                    'secret': decrypt(db_key.api_secret),
                    'key_name': db_key.key_name,
                    'symbols': {},
                    'bots': {},
                    'monitor_flag': False,
                    'monitor_thread': None,
                    'last_balances': {},
                    'last_prices': {},
                    'assets': {},
                    'assets_updated': 0
                }
                try:
                    client = create_client(db_key.platform, self.keys[db_key.id]['api_key'], self.keys[db_key.id]['secret'], testnet=False, timeout=30)
                    self._client_cache[db_key.id] = client
                except Exception as e:
                    logger.error(f"创建客户端失败 key {db_key.id}: {e}")
                    self._client_cache[db_key.id] = None
            configs = SymbolConfigDAO.get_by_api_key(db_key.id)
            for cfg in configs:
                if cfg.is_active:
                    self.keys[db_key.id]['symbols'][cfg.symbol] = {
                        **cfg.config_json,
                        'db_id': cfg.id,
                        'mode': cfg.mode,
                        'manual_avg_price': cfg.manual_avg_price,
                        'avg_price': cfg.avg_price,
                        'quantity': cfg.quantity
                    }
        # 不再自动恢复机器人，交给调度器

    def get_client(self, key_id: int):
        with self._lock:
            client = self._client_cache.get(key_id)
            if client is None:
                key = self.keys.get(key_id)
                if key:
                    try:
                        client = create_client(key['platform'], key['api_key'], key['secret'], testnet=False, timeout=30)
                        self._client_cache[key_id] = client
                    except Exception as e:
                        logger.error(f"创建客户端失败 key {key_id}: {e}")
                        return None
            return client

    def add_key(self, platform: str, key_name: str, api_key: str, secret: str) -> Optional[int]:
        from models.api_key import ApiKey
        from utils.encryption import encrypt
        db_key = ApiKey(
            user_id=self.user_id,
            platform=platform,
            key_name=key_name,
            api_key=encrypt(api_key),
            api_secret=encrypt(secret),
            is_valid=True
        )
        new_id = ApiKeyDAO.create(db_key)
        if new_id:
            with self._lock:
                self.keys[new_id] = {
                    'platform': platform,
                    'api_key': api_key,
                    'secret': secret,
                    'key_name': key_name,
                    'symbols': {},
                    'bots': {},
                    'monitor_flag': False,
                    'monitor_thread': None,
                    'last_balances': {},
                    'last_prices': {},
                    'assets': {},
                    'assets_updated': 0
                }
                try:
                    client = create_client(platform, api_key, secret, testnet=False, timeout=30)
                    self._client_cache[new_id] = client
                except Exception as e:
                    logger.error(f"创建客户端失败 key {new_id}: {e}")
                    self._client_cache[new_id] = None
            return new_id
        return None

    def remove_key(self, key_db_id: int) -> bool:
        with self._lock:
            if key_db_id not in self.keys:
                return False
            for symbol, bot in list(self.keys[key_db_id]['bots'].items()):
                self.stop_bot(key_db_id, symbol)
            self.stop_global_mode(key_db_id)
            learner = self._online_learners.pop(key_db_id, None)
            if learner:
                learner.stop()
            self._risk_managers.pop(key_db_id, None)
            ws = self._ws_managers.pop(key_db_id, None)
            if ws:
                ws.stop()
            client = self._client_cache.pop(key_db_id, None)
            if client and hasattr(client, 'session') and hasattr(client.session, 'close'):
                try:
                    client.session.close()
                except:
                    pass
            del self.keys[key_db_id]
        ApiKeyDAO.delete(key_db_id)
        return True

    def start_all_monitor(self, balance_callback: Callable, price_callback: Optional[Callable] = None):
        with self._lock:
            if self._monitor_running:
                return
            self._monitor_running = True
            self._balance_callbacks.append(balance_callback)
            if price_callback:
                self._price_callbacks.append(price_callback)
            self._stop_monitor.clear()
            self._monitor_thread = threading.Thread(target=self._monitor_all_keys, daemon=True)
            self._monitor_thread.start()
            logger.info("统一监控线程已启动")

    def stop_all_monitor(self):
        self._monitor_running = False
        self._stop_monitor.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
        self._monitor_thread = None
        logger.info("统一监控线程已停止")

    def _monitor_all_keys(self):
        while self._monitor_running and not self._stop_monitor.is_set():
            try:
                for key_id, key in list(self.keys.items()):
                    if not key:
                        continue
                    client = self.get_client(key_id)
                    if not client:
                        continue
                    try:
                        coins = client.get_balances()
                        balances = {}
                        usdt_balance = 0.0
                        for c in coins:
                            coin_name = c.get("coin")
                            if not coin_name:
                                continue
                            available = c.get("availableToWithdraw", "")
                            if available == "":
                                available = c.get("walletBalance", "0")
                            try:
                                qty = float(available)
                            except ValueError:
                                qty = 0.0
                            balances[coin_name] = qty
                            if coin_name == "USDT":
                                usdt_balance = qty
                        with self._lock:
                            if key_id in self.keys:
                                self.keys[key_id]['last_balances'] = balances.copy()
                        for cb in self._balance_callbacks:
                            try:
                                cb(key_id, usdt_balance)
                            except Exception as e:
                                logger.error(f"余额回调失败: {e}")

                        configured_symbols = list(self.keys[key_id]['symbols'].keys())
                        if configured_symbols:
                            prices = {}
                            for sym in configured_symbols:
                                try:
                                    price = client.get_ticker(sym)
                                    if price:
                                        prices[sym] = price
                                except Exception:
                                    pass
                            with self._lock:
                                if key_id in self.keys:
                                    self.keys[key_id]['last_prices'] = prices
                            if self._price_callbacks:
                                for cb in self._price_callbacks:
                                    try:
                                        cb(key_id, prices)
                                    except Exception as e:
                                        logger.error(f"价格回调失败: {e}")

                        # 确保每个 Key 有独立的 RiskManager 和 OnlineLearner
                        if key_id not in self._online_learners:
                            from core.online_learner import OnlineLearner
                            from core.risk_manager import RiskManager
                            learner = OnlineLearner(self.user_id, None)
                            risk_mgr = RiskManager(key_id, self.user_id, online_learner=learner)
                            learner.risk_manager = risk_mgr
                            learner.start()
                            self._online_learners[key_id] = learner
                            self._risk_managers[key_id] = risk_mgr

                        if key_id not in self._ws_managers:
                            from core.websocket_manager import WebSocketManager
                            ws_mgr = WebSocketManager(key['platform'], key['api_key'], key['secret'])
                            ws_mgr.start()
                            self._ws_managers[key_id] = ws_mgr
                            for symbol in self.keys[key_id]['symbols']:
                                ws_mgr.subscribe_trade(symbol, self._on_trade_update)

                    except Exception as e:
                        logger.warning(f"监控 Key {key_id} 失败: {e}")
                    time.sleep(2)
                time.sleep(10)
            except Exception as e:
                logger.error(f"监控线程异常: {e}")
                time.sleep(10)

    def _on_trade_update(self, trade_data):
        from core.market_data_cache import MarketDataCache
        if isinstance(trade_data, list):
            if trade_data and isinstance(trade_data[0], dict):
                symbol = trade_data[0].get('symbol')
        elif isinstance(trade_data, dict):
            symbol = trade_data.get('symbol') or trade_data.get('s')
        else:
            return
        if symbol:
            cache = MarketDataCache()
            cache.update_trade(symbol, trade_data)

    def refresh_key_balance(self, key_db_id: int) -> float:
        key = self.keys.get(key_db_id)
        if not key:
            return 0.0
        client = self.get_client(key_db_id)
        if not client:
            return 0.0
        try:
            coins = client.get_balances()
            usdt_balance = 0.0
            for c in coins:
                if c.get("coin") == "USDT":
                    available = c.get("availableToWithdraw", "")
                    if available == "":
                        available = c.get("walletBalance", "0")
                    usdt_balance = float(available) if available else 0.0
                    break
            with self._lock:
                if key_db_id in self.keys:
                    self.keys[key_db_id]['last_balances']['USDT'] = usdt_balance
            return usdt_balance
        except Exception as e:
            logger.error(f"强制刷新余额失败 key {key_db_id}: {e}")
            return 0.0

    def get_key(self, key_db_id: int) -> Optional[Dict]:
        with self._lock:
            return self.keys.get(key_db_id)

    def get_all_keys(self):
        with self._lock:
            return list(self.keys.keys())

    def set_selected_key(self, key_id: int):
        self._current_selected_key = key_id

    def get_risk_manager(self, key_id: int):
        """获取该 Key 的 RiskManager 实例（供机器人使用）"""
        with self._lock:
            return self._risk_managers.get(key_id)

    def start_bot(self, key_db_id: int, symbol: str, config: dict, mode_display: str,
                  callback: Optional[Callable] = None) -> bool:
        with self._lock:
            key = self.keys.get(key_db_id)
            if not key:
                return False
            if symbol in key['bots'] and key['bots'][symbol].running:
                key['bots'][symbol].stop()
            # 获取该 Key 的 RiskManager（已在监控线程中创建）
            risk_manager = self._risk_managers.get(key_db_id)
            if risk_manager is None:
                logger.error(f"Key {key_db_id} 的 RiskManager 未初始化，无法启动机器人")
                return False
            from services.bot_factory import create_bot
            bot = create_bot(
                platform=key['platform'],
                api_key=key['api_key'],
                secret_key=key['secret'],
                symbol=symbol,
                config=config,
                user_id=self.user_id,
                key_id=key_db_id,
                key_service=self,
                mode_display=mode_display,
                callback=callback,
                risk_manager=risk_manager
            )
            bot._external_mode = True
            bot.running = True
            key['bots'][symbol] = bot
            # 保存配置到数据库
            if 'db_id' not in config:
                from models.symbol_config import SymbolConfig
                session = Session()
                try:
                    existing = session.query(SymbolConfig).filter_by(
                        user_id=self.user_id,
                        api_key_id=key_db_id,
                        platform=key['platform'],
                        symbol=symbol,
                        mode=mode_display
                    ).first()
                    if existing:
                        db_id = existing.id
                    else:
                        new_config = SymbolConfig(
                            user_id=self.user_id,
                            api_key_id=key_db_id,
                            platform=key['platform'],
                            symbol=symbol,
                            category='spot',
                            mode=mode_display,
                            config_json=config,
                            is_active=True
                        )
                        session.add(new_config)
                        session.flush()
                        db_id = new_config.id
                        session.commit()
                    config['db_id'] = db_id
                except Exception as e:
                    logger.error(f"保存配置失败: {e}")
                    session.rollback()
                finally:
                    session.close()
            # 保存配置到内存，只对全局模式设置 mode 字段
            config_copy = config.copy()
            if '全局' in mode_display:
                config_copy['mode'] = 'global'
            else:
                config_copy.pop('mode', None)
            key['symbols'][symbol] = config_copy
            # 注册到调度器
            mode_key = 'expert' if 'AI' in mode_display or '资深' in mode_display else \
                'strategy' if '策略' in mode_display else \
                    'scalping' if '刷单' in mode_display else \
                        'global_sell'
            scheduler = self.schedulers.get(mode_key)
            if scheduler:
                scheduler.register_bot(key_db_id, symbol, bot)
            return True

    def stop_bot(self, key_db_id: int, symbol: str) -> bool:
        with self._lock:
            key = self.keys.get(key_db_id)
            if not key:
                return False
            bot = key['bots'].get(symbol)
            if bot:
                mode_key = 'expert' if 'AI' in bot.mode_display else \
                           'strategy' if '策略' in bot.mode_display else \
                           'scalping' if '刷单' in bot.mode_display else \
                           'global_sell'
                scheduler = self.schedulers.get(mode_key)
                if scheduler:
                    scheduler.unregister_bot(key_db_id, symbol)
                bot.running = False
                del key['bots'][symbol]
                return True
            return False

    def get_bot_status(self, key_db_id: int, symbol: str) -> Optional[Dict]:
        with self._lock:
            key = self.keys.get(key_db_id)
            if key:
                bot = key['bots'].get(symbol)
                if bot:
                    return {
                        'running': bot.running,
                        'position': bot.position.copy(),
                        'mode_display': bot.mode_display
                    }
            return None

    def get_symbols(self, key_db_id: int) -> Dict[str, Dict]:
        with self._lock:
            key = self.keys.get(key_db_id)
            if key:
                return key['symbols'].copy()
            return {}

    def start_global_mode(self, key_db_id: int, config: dict, callback: Optional[Callable] = None) -> bool:
        with self._lock:
            key = self.keys.get(key_db_id)
            if not key:
                return False
            self.stop_global_mode(key_db_id)
            from services.global_mode_service import GlobalModeService
            service = GlobalModeService(self.user_id, key_db_id, self, config, callback)
            service.start()
            self._global_services[key_db_id] = service
            return True

    def stop_global_mode(self, key_db_id: int) -> bool:
        with self._lock:
            service = self._global_services.get(key_db_id)
            if service:
                service.stop()
                service.join(timeout=5)
                del self._global_services[key_db_id]
                return True
            return False

    def is_global_mode_running(self, key_db_id: int) -> bool:
        with self._lock:
            return key_db_id in self._global_services

    def get_online_learner(self, key_id: int):
        with self._lock:
            return self._online_learners.get(key_id)

    # ========== 历史交易同步 ==========
    def sync_trade_history_for_symbol(self, key_id: int, symbol: str, since_days: int = 30):
        """从交易所拉取该币种的历史订单（买入和卖出）并存入本地 Trade 表（去重）"""
        key = self.keys.get(key_id)
        if not key:
            logger.error(f"Key {key_id} 不存在")
            return
        client = self.get_client(key_id)
        if not client:
            logger.error(f"无法获取客户端 key {key_id}")
            return
        try:
            start_time = int((time.time() - since_days * 86400) * 1000)
            orders = client.get_order_history(symbol, limit=200, startTime=start_time)
            if not orders:
                logger.info(f"币种 {symbol} 无历史订单")
                return
            session = Session()
            try:
                inserted = 0
                for order in orders:
                    order_id = str(order.get('orderId') or order.get('order_id'))
                    # 去重
                    existing = session.query(Trade).filter_by(order_id=order_id).first()
                    if existing:
                        continue

                    # 解析方向（兼容不同交易所）
                    side_raw = order.get('side', '')
                    if side_raw in ('Buy', 'BUY'):
                        side = 'buy'
                    elif side_raw in ('Sell', 'SELL'):
                        side = 'sell'
                    else:
                        continue  # 未知方向跳过

                    # 解析价格、数量、金额
                    price = float(order.get('price', 0))
                    qty = float(order.get('cumExecQty', 0) or order.get('executedQty', 0))
                    amount = float(order.get('cumExecValue', 0) or order.get('cummulativeQuoteQty', 0))

                    # 如果金额为0但价格和数量有效，则计算
                    if amount == 0 and price > 0 and qty > 0:
                        amount = price * qty

                    # 如果价格仍为0，尝试从订单中获取平均价格
                    if price == 0 and amount > 0 and qty > 0:
                        price = amount / qty

                    # 时间戳处理
                    timestamp_ms = order.get('timestamp') or order.get('updateTime') or order.get('time')
                    if timestamp_ms:
                        trade_time = datetime.fromtimestamp(timestamp_ms / 1000.0)
                    else:
                        trade_time = datetime.now()

                    trade = Trade(
                        user_id=self.user_id,
                        key_id=key_id,
                        platform=key['platform'],
                        key_name=key.get('key_name', ''),
                        bot_mode='manual_sync',
                        sub_mode='history',
                        symbol=symbol,
                        side=side,
                        price=price,
                        quantity=qty,
                        amount_usdt=amount,
                        fee=0.0,  # 手续费暂不处理
                        order_id=order_id,
                        source_trade_id=order_id,
                        is_manual=True,
                        executed_at=trade_time,
                        created_at=datetime.now()
                    )
                    session.add(trade)
                    inserted += 1
                session.commit()
                if inserted > 0:
                    logger.info(f"同步 {symbol} 历史订单 {inserted} 条 (买入+卖出)")
            except Exception as e:
                session.rollback()
                logger.error(f"同步历史交易失败 {symbol}: {e}")
            finally:
                session.close()
        except Exception as e:
            logger.error(f"获取历史订单失败 {symbol}: {e}")

    # ========== FIFO 成本计算 ==========
    def _get_fifo_avg_price(self, key_id: int, symbol: str) -> Optional[float]:
        session = Session()
        try:
            trades = session.query(Trade).filter(
                Trade.key_id == key_id,
                Trade.symbol == symbol,
                Trade.side.in_(['buy', 'sell'])
            ).order_by(Trade.executed_at.asc()).all()
            if not trades:
                return None
            buy_queue = deque()
            for t in trades:
                if t.side == 'buy':
                    # 买入时实际花费 = amount_usdt + fee? 但 amount_usdt 已是包含手续费的总额？
                    # 为了精确，使用 amount_usdt 作为成本（已包含手续费），数量为 quantity
                    buy_queue.append((t.amount_usdt / t.quantity, t.quantity))
                elif t.side == 'sell':
                    sell_qty = t.quantity
                    while sell_qty > 0 and buy_queue:
                        buy_price, buy_qty = buy_queue[0]
                        if buy_qty <= sell_qty:
                            buy_queue.popleft()
                            sell_qty -= buy_qty
                        else:
                            buy_queue[0] = (buy_price, buy_qty - sell_qty)
                            sell_qty = 0
            if not buy_queue:
                return None
            total_cost = sum(price * qty for price, qty in buy_queue)
            total_qty = sum(qty for _, qty in buy_queue)
            if total_qty == 0:
                return None
            return total_cost / total_qty
        except Exception as e:
            logger.error(f"FIFO 成本计算失败 {symbol}: {e}")
            return None
        finally:
            session.close()

    def _get_fifo_cost_from_exchange(self, key_id: int, symbol: str) -> Optional[float]:
        """直接从交易所获取历史订单，实时计算当前持仓的 FIFO 成本（含手续费）"""
        key = self.keys.get(key_id)
        if not key:
            return None
        client = self.get_client(key_id)
        if not client:
            return None

        try:
            # 获取该币种所有历史订单（最近90天）
            orders = client.get_order_history(symbol, limit=500)
            if not orders:
                return None

            # 获取当前持仓数量（使用 walletBalance）
            balances = client.get_balances()
            base_coin = symbol.replace('USDT', '')
            current_qty = 0.0
            for b in balances:
                if b.get('coin') == base_coin:
                    current_qty = float(b.get('walletBalance', 0))
                    break

            if current_qty <= 0:
                return None

            # 提取买入订单，按时间升序
            buy_orders = []
            for order in orders:
                side = order.get('side', '')
                if side in ('Buy', 'BUY'):
                    price = float(order.get('price', 0))
                    qty = float(order.get('cumExecQty', 0))
                    value = float(order.get('cumExecValue', 0))
                    if value == 0 and price > 0 and qty > 0:
                        value = price * qty
                    timestamp = order.get('timestamp', 0)
                    if qty > 0 and value > 0:
                        buy_orders.append((timestamp, price, qty, value))

            if not buy_orders:
                return None

            buy_orders.sort(key=lambda x: x[0])

            # FIFO 计算
            remaining_qty = current_qty
            total_cost = 0.0
            matched_qty = 0.0
            for ts, price, qty, value in buy_orders:
                if remaining_qty <= 0:
                    break
                if qty <= remaining_qty:
                    total_cost += value
                    matched_qty += qty
                    remaining_qty -= qty
                else:
                    ratio = remaining_qty / qty
                    total_cost += value * ratio
                    matched_qty += remaining_qty
                    remaining_qty = 0
                    break

            if matched_qty == 0:
                return None

            return total_cost / matched_qty
        except Exception as e:
            logger.error(f"从交易所实时计算 FIFO 成本失败 {symbol}: {e}")
            return None

    # ========== 资产管理方法 ==========
    def _start_asset_update_thread(self):
        self._asset_update_running = True
        self._asset_update_thread = threading.Thread(target=self._asset_update_loop, daemon=True)
        self._asset_update_thread.start()

    def _asset_update_loop(self):
        while getattr(self, '_asset_update_running', True):
            try:
                if self._current_selected_key:
                    self.update_assets(self._current_selected_key, force=False)
                time.sleep(30)
            except Exception as e:
                logger.error(f"资产更新线程异常: {e}")
                time.sleep(30)

    def update_assets(self, key_db_id: int, force: bool = False):
        with self._lock:
            key = self.keys.get(key_db_id)
            if not key:
                return
            now = time.time()
            if not force and now - key.get('assets_updated', 0) < 5:
                return

            client = self.get_client(key_db_id)
            if not client:
                return

            try:
                balances = client.get_balances()
                holdings = {}
                for b in balances:
                    coin = b.get('coin')
                    if not coin or coin == 'USDT':
                        continue
                    qty = float(b.get('walletBalance', 0))
                    if qty > 0:
                        holdings[coin] = qty
            except Exception as e:
                logger.error(f"获取余额失败 key {key_db_id}: {e}")
                return

            configs = SymbolConfigDAO.get_by_api_key(key_db_id)
            configured_symbols = {cfg.symbol: cfg for cfg in configs if cfg.is_active}

            all_base_coins = set(configured_symbols.keys()) | set(holdings.keys())
            usdt_pairs = {base + 'USDT' for base in all_base_coins}
            for symbol in configured_symbols:
                if symbol not in usdt_pairs:
                    usdt_pairs.add(symbol)

            assets = {}
            for symbol in usdt_pairs:
                base_coin = symbol.replace('USDT', '')
                try:
                    price = client.get_ticker(symbol)
                    if not price:
                        continue
                except Exception:
                    continue

                qty = holdings.get(base_coin, 0.0)
                value = qty * price

                if value < 1.0 and symbol not in configured_symbols:
                    continue

                avg_cost = self._get_fifo_avg_price_from_exchange(key_db_id, symbol)
                total_pnl = self._get_total_pnl_from_exchange(key_db_id, symbol)

                if symbol in configured_symbols and qty == 0:
                    assets[symbol] = {
                        'qty': 0.0,
                        'price': price,
                        'value': 0.0,
                        'pnl_usdt': 0.0,
                        'pnl_pct': 0.0,
                        'cost': avg_cost if avg_cost else 0.0,
                        'total_pnl': total_pnl
                    }
                    continue

                if qty <= 0:
                    continue

                if avg_cost is None or avg_cost <= 0:
                    continue

                pnl = (price - avg_cost) * qty
                pnl_pct = (price - avg_cost) / avg_cost * 100 if avg_cost else 0
                assets[symbol] = {
                    'qty': qty,
                    'price': price,
                    'value': value,
                    'pnl_usdt': pnl,
                    'pnl_pct': pnl_pct,
                    'cost': avg_cost,
                    'total_pnl': total_pnl
                }

            key['assets'] = assets
            key['assets_updated'] = time.time()

    def _get_total_pnl_from_exchange(self, key_id: int, symbol: str) -> float:
        """从交易所获取所有历史订单，计算已实现盈亏（总盈亏）"""
        key = self.keys.get(key_id)
        if not key:
            return 0.0
        client = self.get_client(key_id)
        if not client:
            return 0.0

        try:
            orders = client.get_order_history(symbol, limit=1000)
            if not orders:
                logger.debug(f"{symbol} 无历史订单，总盈亏为0")
                return 0.0

            # 分离买入和卖出订单，按时间升序
            buy_orders = []
            sell_orders = []
            for order in orders:
                side = order.get('side', '')
                price = float(order.get('price', 0))
                qty = float(order.get('cumExecQty', 0))
                value = float(order.get('cumExecValue', 0))
                if value == 0 and price > 0 and qty > 0:
                    value = price * qty
                timestamp = order.get('timestamp', 0)
                if qty <= 0 or value <= 0:
                    continue
                if side in ('Buy', 'BUY'):
                    buy_orders.append((timestamp, price, qty, value))
                elif side in ('Sell', 'SELL'):
                    sell_orders.append((timestamp, price, qty, value))

            if not sell_orders:
                return 0.0

            # 按时间排序
            buy_orders.sort(key=lambda x: x[0])
            sell_orders.sort(key=lambda x: x[0])

            from collections import deque
            queue = deque()  # 存储买入订单 (price, qty, value)
            total_pnl = 0.0
            i = j = 0
            while i < len(buy_orders) or j < len(sell_orders):
                buy_time = buy_orders[i][0] if i < len(buy_orders) else float('inf')
                sell_time = sell_orders[j][0] if j < len(sell_orders) else float('inf')
                if buy_time <= sell_time:
                    _, price, qty, value = buy_orders[i]
                    queue.append((price, qty, value))
                    i += 1
                else:
                    _, sell_price, sell_qty, sell_value = sell_orders[j]
                    remaining = sell_qty
                    cost = 0.0
                    while remaining > 0 and queue:
                        buy_price, buy_qty, buy_value = queue[0]
                        if buy_qty <= remaining:
                            cost += buy_value
                            remaining -= buy_qty
                            queue.popleft()
                        else:
                            ratio = remaining / buy_qty
                            cost += buy_value * ratio
                            queue[0] = (buy_price, buy_qty - remaining, buy_value * (1 - ratio))
                            remaining = 0
                    if cost > 0:
                        total_pnl += sell_value - cost
                    j += 1
            return total_pnl
        except Exception as e:
            logger.error(f"总盈亏计算失败 {symbol}: {e}")
            return 0.0

    def _auto_sync_and_recalc(self, key_db_id: int, symbols: list):
        def do_sync():
            for symbol in symbols:
                self.sync_trade_history_for_symbol(key_db_id, symbol, since_days=30)
            self.update_assets(key_db_id, force=True)
        threading.Thread(target=do_sync, daemon=True).start()

    def _get_total_pnl(self, key_id: int, symbol: str) -> float:
        """从本地 trade 表计算该币种所有已卖出交易的总盈亏（已实现盈亏）"""
        from dao.trade_dao import TradeDAO
        from models.trade import Trade
        from utils.db import Session
        session = Session()
        try:
            trades = session.query(Trade).filter(
                Trade.key_id == key_id,
                Trade.symbol == symbol,
                Trade.side == 'sell'
            ).all()
            total = sum(t.pnl or 0.0 for t in trades)
            return total
        except Exception as e:
            logger.error(f"计算总盈亏失败 {symbol}: {e}")
            return 0.0
        finally:
            session.close()

    def get_asset(self, key_db_id: int, symbol: str) -> Optional[Dict]:
        with self._lock:
            key = self.keys.get(key_db_id)
            if not key:
                return None
            return key.get('assets', {}).get(symbol)

    def force_sell_symbol(self, key_id: int, symbol: str) -> bool:
        import math
        key = self.keys.get(key_id)
        if not key:
            error_msg = f"Key {key_id} 不存在"
            logger.error(error_msg)
            print(error_msg)
            return False
        client = self.get_client(key_id)
        if not client:
            error_msg = f"无法获取客户端 key {key_id}"
            logger.error(error_msg)
            print(error_msg)
            return False
        try:
            # 获取持仓数量
            balances = client.get_balances()
            base_coin = symbol.replace('USDT', '')
            qty = 0.0
            for b in balances:
                if b.get('coin') == base_coin:
                    qty = float(b.get('walletBalance', 0))
                    break
            if qty <= 0:
                logger.info(f"{symbol} 无持仓，无需卖出")
                return True

            # 获取最小交易步长和精度
            step, _ = client.get_symbol_info(symbol)
            step_str = str(step).rstrip('0')
            if '.' in step_str:
                decimals = len(step_str.split('.')[1])
            else:
                decimals = 0
            raw_qty = math.floor(qty / step) * step
            if raw_qty <= 0:
                logger.warning(f"{symbol} 可卖数量为0")
                return False
            formatted_qty = round(raw_qty, decimals)
            if formatted_qty <= 0:
                logger.warning(f"{symbol} 格式化后数量为0")
                return False

            price = client.get_ticker(symbol)
            if not price:
                logger.error(f"无法获取 {symbol} 价格")
                return False

            min_order = 5.0
            if formatted_qty * price < min_order:
                logger.warning(f"{symbol} 卖出价值 {formatted_qty * price:.2f} USDT 小于最小订单额 {min_order}")
                return False

            # 执行市价卖出
            order_id = client.market_sell(symbol, formatted_qty)
            if not order_id:
                logger.error(f"强制卖出 {symbol} 下单失败，订单ID为空")
                return False

            sell_value = formatted_qty * price
            fee = sell_value * 0.001
            from services.trade_service import record_trade
            record_trade(
                user_id=self.user_id,
                key_id=key_id,
                bot_mode='manual',
                sub_mode='force_sell',
                symbol=symbol,
                side='sell',
                price=price,
                quantity=formatted_qty,
                amount_usdt=sell_value,
                fee=fee,
                order_id=order_id,
                is_manual=True,
                exit_reason='force_clear'
            )
            # 停止机器人并清理数据库
            self.stop_bot(key_id, symbol)
            configs = SymbolConfigDAO.get_by_api_key(key_id)
            for cfg in configs:
                if cfg.symbol == symbol:
                    SymbolConfigDAO.clear_position(cfg.id)
                    cfg.quantity = None
                    cfg.avg_price = None
                    session = Session()
                    try:
                        session.merge(cfg)
                        session.commit()
                    except Exception as e:
                        logger.error(f"清理数据库持仓失败: {e}")
                    finally:
                        session.close()
                    break
            self.update_assets(key_id, force=True)
            logger.info(f"强制卖出 {symbol} 成功，数量 {formatted_qty:.6f}，价值 {sell_value:.2f} USDT")
            print(f"强制卖出 {symbol} 成功，数量 {formatted_qty:.6f}，价值 {sell_value:.2f} USDT")
            return True
        except Exception as e:
            error_msg = f"强制卖出 {symbol} 失败: {e}"
            logger.error(error_msg)
            print(error_msg)
            import traceback
            traceback.print_exc()
            return False

    def _get_fifo_avg_price_from_exchange(self, key_id: int, symbol: str) -> Optional[float]:
        """从交易所获取历史订单，通过 FIFO 计算当前持仓的平均成本"""
        key = self.keys.get(key_id)
        if not key:
            return None
        client = self.get_client(key_id)
        if not client:
            return None

        try:
            orders = client.get_order_history(symbol, limit=1000)
            if not orders:
                return None

            balances = client.get_balances()
            base_coin = symbol.replace('USDT', '')
            current_qty = 0.0
            for b in balances:
                if b.get('coin') == base_coin:
                    current_qty = float(b.get('walletBalance', 0))
                    break
            if current_qty <= 0:
                return None

            from collections import deque
            queue = deque()

            for order in orders:
                side = order.get('side', '')
                if side in ('Buy', 'BUY'):
                    price = float(order.get('price', 0))
                    qty = float(order.get('cumExecQty', 0))
                    value = float(order.get('cumExecValue', 0))
                    if value == 0 and price > 0 and qty > 0:
                        value = price * qty
                    if qty > 0 and value > 0:
                        queue.append((price, qty, value))
                elif side in ('Sell', 'SELL'):
                    sell_qty = float(order.get('cumExecQty', 0))
                    if sell_qty <= 0:
                        continue
                    while sell_qty > 0 and queue:
                        buy_price, buy_qty, buy_value = queue[0]
                        if buy_qty <= sell_qty:
                            queue.popleft()
                            sell_qty -= buy_qty
                        else:
                            ratio = sell_qty / buy_qty
                            new_qty = buy_qty - sell_qty
                            new_value = buy_value * (1 - ratio)
                            queue[0] = (buy_price, new_qty, new_value)
                            sell_qty = 0

            if not queue:
                return None

            total_cost = sum(v for _, _, v in queue)
            total_qty = sum(q for _, q, _ in queue)
            if total_qty == 0:
                return None

            return total_cost / total_qty
        except Exception as e:
            logger.error(f"FIFO 成本计算失败 {symbol}: {e}")
            return None

    def stop(self):
        self.stop_all_monitor()
        self._asset_update_running = False
        if hasattr(self, '_asset_update_thread') and self._asset_update_thread:
            self._asset_update_thread.join(timeout=2)
        for key_id in list(self.keys.keys()):
            self.keys[key_id]['monitor_flag'] = False
            client = self._client_cache.pop(key_id, None)
            if client and hasattr(client, 'session') and hasattr(client.session, 'close'):
                try:
                    client.session.close()
                except:
                    pass