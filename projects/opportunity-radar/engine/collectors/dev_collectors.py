"""开发者/开源赛道采集器：从 GitHub 搜索 API 抓"近期爆款开源项目"。

机会类型（按 build/06-机会的定义.md 的 L1-L4 分级思路）：
- L4 即时可行动：近期新建且高 star 的项目（值得马上看/用）。
- L3 待评估：star 增长快但还不算爆款。

这是"早发现新工具"的一手信号——技术圈/开发者最关心的信息差。
GitHub 搜索 API 无需 key（未认证有较低速率限制，对 MVP 够用）。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.base import Collector, insert_signal  # noqa: E402
from config import config  # noqa: E402

TRACK = "开发者开源"


def _client() -> httpx.Client:
    return httpx.Client(
        timeout=config.HTTP_TIMEOUT,
        headers={"User-Agent": config.USER_AGENT, "Accept": "application/vnd.github+json"},
    )


class GitHubRising(Collector):
    """GitHub 搜索：最近 30 天内新建 + star 数过百 的项目（"新晋爆款"）。

    阈值可按 stars 区分等级（filter.py 会基于 metric_value 进一步分级）。
    """
    name = "GitHub 新晋爆款"
    type = "api"
    track = TRACK
    layer = 1
    rating = 3

    DAYS = 30          # 看过去多少天的新仓库
    MIN_STARS = 100    # 至少多少 star 才算"爆款"
    PER_PAGE = 30

    def collect(self, conn) -> tuple[int, int]:
        since = (datetime.now(timezone.utc) - timedelta(days=self.DAYS)).date().isoformat()
        url = (
            "https://api.github.com/search/repositories"
            f"?q=created:%3E{since}+stars:%3E{self.MIN_STARS}"
            f"&sort=stars&order=desc&per_page={self.PER_PAGE}"
        )
        with _client() as c:
            data = c.get(url).json()
        items = data.get("items", [])
        ins = skip = 0
        for r in items:
            stars = r.get("stargazers_count", 0)
            lang = r.get("language") or "—"
            desc = (r.get("description") or "")[:300]
            full = r.get("full_name", "")
            title = f"[新晋开源] {full} · {stars}⭐ · {lang}"
            content = (
                f"项目: {full}\n语言: {lang}\nStars: {stars}\n"
                f"创建于: {r.get('created_at','')[:10]} | 最后推送: {r.get('pushed_at','')[:10]}\n"
                f"描述: {desc}\n"
                f"机会角度: 早期介入还能享受信息差；评估它解决的问题是否符合受众需求。"
            )
            ok = insert_signal(
                conn, source_id=self._source_id, track=TRACK, signal_type="trending",
                title=title, content=content, url=r.get("html_url", ""),
                metric_value=float(stars), metric_label="Stars",
                published=r.get("created_at"),
                dedup_key=f"gh:{full}",
            )
            ins += ok
            skip += not ok
        return ins, skip


DEV_COLLECTORS = [GitHubRising]
