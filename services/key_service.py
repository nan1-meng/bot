# 文件路径: services/key_service.py
import threading
import time
from typing import Dict, Optional, Callable, Any
from dao.api_key_dao import ApiKeyDAO
from dao.symbol_config_dao import SymbolConfigDAO
from utils.encryption import decrypt
from clients import create_client
from utils.logger import get_logger

logger = get_logger(__name__)

class KeyService:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.keys: Dict[int, Dict] = {}
        self._lock = threading.RLock()
        self._global_services: Dict[int, Any] = {}
        self._online_learners: Dict[int, Any] = {}
        self._ws_managers: Dict[int, Any] = {}   # 每个 Key 独立 WebSocket 管理器
        self._client_cache: Dict[int, Any] = {}  # 缓存交易所客户端实例

        # 统一监控线程
        self._monitor_running = False
        self._monitor_thread = None
        self._stop_monitor = threading.Event()
        self._balance_callbacks = []
        self._price_callbacks = []

        # 资产更新线程
        self._asset_update_running = True
        self._asset_update_thread = None

        self.load_from_db()
        self._start_asset_update_thread()

    def load_from_db(self):
        db_keys = ApiKeyDAO.get_by_user(self.user_id)
        for db_key in db_keys:
            with self._lock:
                self.keys[db_key.id] = {
                    'platform': db_key.platform,
                    'api_key': decrypt(db_key.api_key),
                    'secret': decrypt(db_key.api_secret),
                    'symbols': {},
                    'bots': {},
                    'monitor_flag': False,
                    'monitor_thread': None,
                    'last_balances': {},
                    'last_prices': {},
                    'assets': {},
                    'assets_updated': 0
                }
                # 创建并缓存客户端实例
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
        self._restore_bots()

    def get_client(self, key_id: int):
        """获取缓存的交易所客户端，若不存在则创建"""
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

    def _restore_bots(self):
        for key_id, key in self.keys.items():
            platform = key['platform']
            api_key = key['api_key']
            secret = key['secret']
            for symbol, config in key['symbols'].items():
                mode = config.get('mode')
                if mode == 'global':
                    from bots.global_sell_bot import GlobalSellBot
                    bot = GlobalSellBot(
                        platform=platform,
                        api_key=api_key,
                        secret_key=secret,
                        symbol=symbol,
                        config=config,
                        user_id=self.user_id,
                        key_id=key_id,
                        key_service=self,
                        mode_display="全局模式",
                        callback=self._global_callback
                    )
                    bot._load_position_from_db()
                    bot.start()
                    key['bots'][symbol] = bot

    def _global_callback(self, key_id, symbol, signal_type, price, timestamp, msg=None):
        pass

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
                    'symbols': {},
                    'bots': {},
                    'monitor_flag': False,
                    'monitor_thread': None,
                    'last_balances': {},
                    'last_prices': {},
                    'assets': {},
                    'assets_updated': 0
                }
                # 创建客户端
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
                bot.stop()
            self.stop_global_mode(key_db_id)
            # 停止学习器
            learner = self._online_learners.pop(key_db_id, None)
            if learner:
                learner.stop()
            # 停止 WebSocket
            ws = self._ws_managers.pop(key_db_id, None)
            if ws:
                ws.stop()
            # 关闭客户端
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
        """启动一个后台线程，监控所有 Key 的余额和价格"""
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
        """停止监控线程"""
        self._monitor_running = False
        self._stop_monitor.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
        self._monitor_thread = None
        logger.info("统一监控线程已停止")

    def _monitor_all_keys(self):
        """循环获取所有 Key 的余额和价格（使用缓存客户端）"""
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

                        # 更新价格（仅对已配置的币种）
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

                        # 启动在线学习器（如果尚未启动）
                        if key_id not in self._online_learners:
                            from core.online_learner import OnlineLearner
                            from core.risk_manager import RiskManager
                            learner = OnlineLearner(self.user_id, None)
                            risk_mgr = RiskManager(key_id, self.user_id, online_learner=learner)
                            learner.risk_manager = risk_mgr
                            learner.start()
                            self._online_learners[key_id] = learner

                        # 启动 WebSocket 管理器（如果尚未启动）
                        if key_id not in self._ws_managers:
                            from core.websocket_manager import WebSocketManager
                            ws_mgr = WebSocketManager(key['platform'], key['api_key'], key['secret'])
                            ws_mgr.start()
                            self._ws_managers[key_id] = ws_mgr
                            # 订阅已配置币种的成交数据
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
        """WebSocket 成交数据回调"""
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

    def start_bot(self, key_db_id: int, symbol: str, config: dict, mode_display: str, callback: Optional[Callable] = None) -> bool:
        with self._lock:
            key = self.keys.get(key_db_id)
            if not key:
                return False
            if symbol in key['bots'] and key['bots'][symbol].running:
                key['bots'][symbol].stop()
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
                callback=callback
            )
            bot.start()
            key['bots'][symbol] = bot
            if 'db_id' not in config:
                from models.symbol_config import SymbolConfig
                from utils.db import Session
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
            key['symbols'][symbol] = config

            # 订阅 WebSocket 成交数据
            if key_db_id in self._ws_managers:
                self._ws_managers[key_db_id].subscribe_trade(symbol, self._on_trade_update)

            return True

    def stop_bot(self, key_db_id: int, symbol: str) -> bool:
        with self._lock:
            key = self.keys.get(key_db_id)
            if not key:
                return False
            bot = key['bots'].get(symbol)
            if bot and bot.running:
                bot.stop()
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

    # ========== 资产管理方法 ==========
    def _start_asset_update_thread(self):
        self._asset_update_running = True
        self._asset_update_thread = threading.Thread(target=self._asset_update_loop, daemon=True)
        self._asset_update_thread.start()

    def _asset_update_loop(self):
        while getattr(self, '_asset_update_running', True):
            try:
                for key_id in list(self.keys.keys()):
                    self.update_assets(key_id, force=True)
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

            from dao.symbol_config_dao import SymbolConfigDAO
            configs = SymbolConfigDAO.get_by_api_key(key_db_id)
            if not configs:
                key['assets'] = {}
                return

            client = self.get_client(key_db_id)
            if not client:
                return

            try:
                assets = {}
                for cfg in configs:
                    if not cfg.avg_price or not cfg.quantity or cfg.quantity <= 0:
                        continue
                    symbol = cfg.symbol
                    try:
                        price = client.get_ticker(symbol)
                        if not price:
                            continue
                    except Exception:
                        continue
                    qty = cfg.quantity
                    cost = cfg.avg_price
                    pnl = (price - cost) * qty
                    pnl_pct = (price - cost) / cost * 100 if cost else 0
                    assets[symbol] = {
                        'qty': qty,
                        'price': price,
                        'value': qty * price,
                        'pnl_usdt': pnl,
                        'pnl_pct': pnl_pct,
                        'cost': cost
                    }
                key['assets'] = assets
                key['assets_updated'] = time.time()
            except Exception as e:
                logger.error(f"更新资产失败 key={key_db_id}: {e}")

    def get_asset(self, key_db_id: int, symbol: str) -> Optional[Dict]:
        with self._lock:
            key = self.keys.get(key_db_id)
            if not key:
                return None
            return key.get('assets', {}).get(symbol)

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