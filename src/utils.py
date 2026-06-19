"""
公共工具函数模块

提供跨模块复用的工具函数：
  - _read_windows_env_var: 读取 Windows 注册表环境变量
  - get_api_key: 多级优先级获取 API Key
"""

import logging
import os
import subprocess
import sys

logger = logging.getLogger("utils")
logger.setLevel(logging.INFO)

if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_handler)


def _read_windows_env_var(name):
    if sys.platform != "win32":
        return ""
    try:
        for scope in ["User", "Machine"]:
            ps_cmd = f'[System.Environment]::GetEnvironmentVariable("{name}","{scope}")'
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=10
            )
            val = r.stdout.strip()
            if val:
                return val
    except Exception:
        pass
    return ""


def get_api_key(env_var_name="DASHSCOPE_API_KEY"):
    api_key = os.getenv(env_var_name, "").strip()
    if not api_key:
        api_key = _read_windows_env_var(env_var_name)
    if not api_key:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv(env_var_name, "").strip()
    if not api_key:
        logger.error("[utils] 未找到 %s，请在系统环境变量或 .env 文件中配置", env_var_name)
        raise ValueError(f"{env_var_name} 未配置")
    return api_key