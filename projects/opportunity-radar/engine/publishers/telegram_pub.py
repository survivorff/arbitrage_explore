"""Telegram 推送：支持"一个频道一个赛道"的路由。

配置（.env）：
    RADAR_TG_ENABLED=true
    RADAR_TG_BOT_TOKEN=123456:ABC...
    # 全局默认（可选，私聊调试用）
    RADAR_TG_CHAT_ID=5307818537
    # 按赛道路由（推荐，一个频道一个赛道）：RADAR_TG_CHAT_<赛道key大写>
    RADAR_TG_CHAT_CRYPTO=@survivorff_crypto_opp
    RADAR_TG_CHAT_AI=@your_ai_channel
    RADAR_TG_CHAT_DEV=@your_dev_channel

推送某赛道时优先用该赛道的频道；没配则回退到全局 RADAR_TG_CHAT_ID。
未配置时优雅跳过。
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import config  # noqa: E402
from publishers.exporters import export_single_telegram  # noqa: E402

# 赛道名(中文) → 配置 key 后缀
TRACK_KEY = {"加密Web3": "CRYPTO", "AI工具": "AI", "开发者开源": "DEV"}


def _enabled() -> bool:
    return os.environ.get("RADAR_TG_ENABLED", "false").lower() in ("1", "true", "yes")


def _token() -> str:
    return os.environ.get("RADAR_TG_BOT_TOKEN", "")


def chat_for_track(track: str | None, allow_fallback: bool = True) -> str:
    """按赛道取频道。allow_fallback=False 时，没有专属频道就返回空（不回退全局）。"""
    if track:
        key = TRACK_KEY.get(track)
        if key:
            specific = os.environ.get(f"RADAR_TG_CHAT_{key}", "")
            if specific:
                return specific
    if allow_fallback:
        return os.environ.get("RADAR_TG_CHAT_ID", "")
    return ""


def tg_ready(track: str | None = None) -> bool:
    return _enabled() and bool(_token()) and bool(chat_for_track(track))


def send_message(text: str, chat_id: str) -> tuple[bool, str]:
    if not _enabled() or not _token() or not chat_id:
        return False, "Telegram 未配置（检查 RADAR_TG_ENABLED / TOKEN / CHAT）"
    url = f"https://api.telegram.org/bot{_token()}/sendMessage"
    payload = {
        "chat_id": chat_id,
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


def publish_opportunities(opps: list[dict], track: str | None = None) -> dict:
    """推送机会列表。track 指定时推到该赛道频道；否则按每条机会自己的赛道路由。"""
    stats = {"sent": 0, "failed": 0, "skipped": False, "errors": []}
    if not _enabled() or not _token():
        stats["skipped"] = True
        return stats
    for o in opps:
        chat = chat_for_track(track or o.get("track"))
        if not chat:
            stats["failed"] += 1
            stats["errors"].append(f"无频道配置: {o.get('track')}")
            continue
        ok, msg = send_message(export_single_telegram(o), chat)
        if ok:
            stats["sent"] += 1
        else:
            stats["failed"] += 1
            stats["errors"].append(msg)
        time.sleep(0.4)
    return stats


if __name__ == "__main__":
    # 测试：给加密频道发一条
    chat = chat_for_track("加密Web3")
    if _enabled() and _token() and chat:
        ok, msg = send_message(f"🛰️ 机会雷达 · 加密频道推送测试（目标 {chat}）：连接正常。", chat)
        print(f"测试发送到 {chat}: {ok} - {msg}")
    else:
        print("加密频道未配置。请在 .env 设置 RADAR_TG_CHAT_CRYPTO=@你的频道。")
