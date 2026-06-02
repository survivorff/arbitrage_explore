"""Telegram 推送：把机会推送到 Telegram 频道/群/个人。

配置（.env）：
    RADAR_TG_ENABLED=true
    RADAR_TG_BOT_TOKEN=123456:ABC...      （找 @BotFather 创建 bot 获取）
    RADAR_TG_CHAT_ID=@your_channel 或 数字chat_id

未配置时优雅跳过（和 AI 一样）。加密/开发者受众天然在 Telegram，这是最值得做的自动渠道。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import config  # noqa: E402
from publishers.exporters import export_single_telegram  # noqa: E402


def _tg_config() -> dict:
    return {
        "enabled": os.environ.get("RADAR_TG_ENABLED", "false").lower() in ("1", "true", "yes"),
        "token": os.environ.get("RADAR_TG_BOT_TOKEN", ""),
        "chat_id": os.environ.get("RADAR_TG_CHAT_ID", ""),
    }


def tg_ready() -> bool:
    c = _tg_config()
    return c["enabled"] and bool(c["token"]) and bool(c["chat_id"])


def send_message(text: str) -> tuple[bool, str]:
    """发送一条消息。返回 (成功, 说明)。"""
    c = _tg_config()
    if not tg_ready():
        return False, "Telegram 未配置（设置 RADAR_TG_ENABLED / TOKEN / CHAT_ID）"
    url = f"https://api.telegram.org/bot{c['token']}/sendMessage"
    payload = {
        "chat_id": c["chat_id"],
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }
    try:
        resp = httpx.post(url, json=payload, timeout=config.HTTP_TIMEOUT)
        if resp.status_code == 200:
            return True, "发送成功"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, f"异常: {e}"


def publish_opportunities(opps: list[dict]) -> dict:
    """逐条推送机会到 Telegram。返回统计。"""
    stats = {"sent": 0, "failed": 0, "skipped": False, "errors": []}
    if not tg_ready():
        stats["skipped"] = True
        return stats
    for o in opps:
        ok, msg = send_message(export_single_telegram(o))
        if ok:
            stats["sent"] += 1
        else:
            stats["failed"] += 1
            stats["errors"].append(msg)
    return stats


if __name__ == "__main__":
    if tg_ready():
        ok, msg = send_message("🛰️ 机会雷达 Telegram 推送测试：连接正常。")
        print(f"测试发送: {ok} - {msg}")
    else:
        print("Telegram 未配置。请在 .env 设置 RADAR_TG_ENABLED / RADAR_TG_BOT_TOKEN / RADAR_TG_CHAT_ID。")
