# 文件路径: strategies/loader.py
"""
动态加载自定义策略
允许用户将自己的策略模块放入 strategies/custom/ 目录并自动加载
"""
import importlib
import os
from typing import Dict, Any, Optional
from .base import Strategy

CUSTOM_STRATEGY_PATH = "strategies.custom"

def load_custom_strategy(name: str, params: Dict[str, Any] = None) -> Optional[Strategy]:
    """
    尝试从自定义模块加载策略
    name: 策略名称（同时也是模块名，如 "my_strategy"）
    要求模块中存在一个名为 MyStrategy 的类（首字母大写驼峰），且继承自 Strategy
    """
    try:
        module_name = f"{CUSTOM_STRATEGY_PATH}.{name.lower()}"
        module = importlib.import_module(module_name)
        class_name = name.title().replace('_', '')
        strategy_class = getattr(module, class_name, None)
        if strategy_class and issubclass(strategy_class, Strategy):
            return strategy_class(params)
        else:
            raise ImportError(f"无法找到策略类 {class_name}")
    except Exception as e:
        # 静默失败，返回 None
        return None

def list_custom_strategies() -> list:
    """列出所有可用的自定义策略名称"""
    strategies = []
    custom_dir = os.path.join(os.path.dirname(__file__), "custom")
    if not os.path.exists(custom_dir):
        return []
    for file in os.listdir(custom_dir):
        if file.endswith(".py") and not file.startswith("__"):
            name = file[:-3]
            strategies.append(name)
    return strategies