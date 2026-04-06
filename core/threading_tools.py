# 文件路径: core/threading_tools.py
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

class GlobalThreadPool:
    _instance = None
    _lock = threading.Lock()
    def __init__(self, max_workers: int = 16):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    @classmethod
    def instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance
    def submit(self, fn: Callable, *args, **kwargs):
        return self.executor.submit(fn, *args, **kwargs)

class SafeLoopThread(threading.Thread):
    def __init__(self, name: str, target_tick: Callable, interval: float = 1.0, on_error: Optional[Callable] = None, daemon: bool = True):
        super().__init__(name=name, daemon=daemon)
        self._target_tick = target_tick
        self._interval = max(0.1, interval)
        self._on_error = on_error
        self._running = threading.Event(); self._running.set()
        self.last_heartbeat = time.time()
    def stop(self):
        self._running.clear()
    def is_running(self):
        return self._running.is_set()
    def run(self):
        while self._running.is_set():
            started = time.time()
            try:
                self._target_tick()
            except Exception as e:
                if self._on_error:
                    self._on_error(e)
                else:
                    print(f"[SafeLoopThread:{self.name}] error: {e}")
                    traceback.print_exc()
            finally:
                self.last_heartbeat = time.time()
            spent = time.time() - started
            sleep_for = self._interval - spent
            time.sleep(sleep_for if sleep_for > 0 else 0.05)
