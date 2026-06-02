"""赛道定义：每个赛道声明自己用哪些数据源/采集器。

这是回应"不同赛道数据源不同"的核心设计：
- 加密Web3：用一手数据 API（DeFi收益率、资金费率、趋势），外加少量公告类。
- AI工具：用资讯 RSS（厂商博客、社区、媒体）——因为 AI 机会主要以"文章"形式出现。

要新增赛道，只需在这里加一个 Track，声明它的采集器即可。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collectors.crypto_collectors import CRYPTO_COLLECTORS  # noqa: E402
from collectors.dev_collectors import DEV_COLLECTORS  # noqa: E402


class Track:
    def __init__(self, key: str, name: str, desc: str,
                 api_collectors=None, rss_track: str | None = None):
        self.key = key
        self.name = name
        self.desc = desc
        self.api_collectors = api_collectors or []   # 数据类采集器（类列表）
        self.rss_track = rss_track                    # 若有 RSS 源，用此 track 名匹配 sources 表


# ---- 赛道注册表 ----
TRACKS: dict[str, Track] = {
    "crypto": Track(
        key="crypto",
        name="加密Web3",
        desc="链上收益率、资金费率、趋势、新币上线等一手数据机会（API 为主）",
        api_collectors=CRYPTO_COLLECTORS,
        rss_track="加密Web3",
    ),
    "ai": Track(
        key="ai",
        name="AI工具",
        desc="AI 工具/模型/红利资讯（RSS 为主）",
        api_collectors=[],
        rss_track="AI工具",
    ),
    "dev": Track(
        key="dev",
        name="开发者开源",
        desc="GitHub 新晋爆款开源项目 + 技术社区一手讨论（API + 社区 RSS）",
        api_collectors=DEV_COLLECTORS,
        rss_track="开发者开源",
    ),
}


def get_track(key: str) -> Track | None:
    return TRACKS.get(key)


def list_tracks() -> list[Track]:
    return list(TRACKS.values())
