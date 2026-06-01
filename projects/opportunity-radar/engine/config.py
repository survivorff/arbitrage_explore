"""配置加载：从 .env / 环境变量读取，零外部依赖（手写 .env 解析）。

密钥只从环境变量/.env 读取，绝不硬编码、绝不入库。
"""
from __future__ import annotations

import os
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """极简 .env 解析，不覆盖已存在的环境变量。"""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(ENGINE_DIR / ".env")


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _get_bool(name: str, default: bool = False) -> bool:
    return _get(name, str(default)).lower() in ("1", "true", "yes", "on")


def _get_int(name: str, default: int) -> int:
    try:
        return int(_get(name, str(default)))
    except ValueError:
        return default


class Config:
    # AI
    AI_ENABLED: bool = _get_bool("RADAR_AI_ENABLED", False)
    AI_BASE_URL: str = _get("RADAR_AI_BASE_URL", "https://api.openai.com/v1")
    AI_API_KEY: str = _get("RADAR_AI_API_KEY", "")
    AI_MODEL: str = _get("RADAR_AI_MODEL", "gpt-4o-mini")

    # DB —— 相对路径则放在 engine 目录下
    _db_raw: str = _get("RADAR_DB_PATH", "radar.db")
    DB_PATH: str = str(ENGINE_DIR / _db_raw) if not os.path.isabs(_db_raw) else _db_raw

    # 采集
    FETCH_LIMIT: int = _get_int("RADAR_FETCH_LIMIT", 50)
    HTTP_TIMEOUT: int = _get_int("RADAR_HTTP_TIMEOUT", 20)
    USER_AGENT: str = _get("RADAR_USER_AGENT", "opportunity-radar/0.1 (personal research)")

    # 赛道
    TRACK: str = _get("RADAR_TRACK", "AI工具")

    @classmethod
    def ai_ready(cls) -> bool:
        return cls.AI_ENABLED and bool(cls.AI_API_KEY)


config = Config()
