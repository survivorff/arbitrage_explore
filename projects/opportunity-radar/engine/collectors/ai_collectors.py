"""AI 工具赛道的 API 采集器：抓"最新最热"的一手信号。

RSS 给的是综合资讯，这里补充真正的热度信号：
- HuggingFace trending 模型  → AI 圈最热的新模型（带 likes/下载量）
- HuggingFace trending Spaces → 最热的 AI 应用/demo
- HN Algolia 高分 AI 讨论     → 技术圈在热议什么 AI（稳定替代 HN-AI RSS）

全部免费、无需 key。
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.base import Collector, insert_signal  # noqa: E402
from config import config  # noqa: E402

TRACK = "AI工具"


def _client() -> httpx.Client:
    return httpx.Client(
        timeout=config.HTTP_TIMEOUT,
        headers={"User-Agent": config.USER_AGENT, "Accept": "application/json"},
    )


class HFTrendingModels(Collector):
    """HuggingFace 热门模型：AI 圈最热的新模型。"""
    name = "HuggingFace 热门模型"
    type = "api"
    track = TRACK
    layer = 1
    rating = 3
    TOP_N = 20

    def collect(self, conn) -> tuple[int, int]:
        with _client() as c:
            data = c.get(
                "https://huggingface.co/api/models?sort=trendingScore&limit=%d" % self.TOP_N
            ).json()
        ins = skip = 0
        for m in data:
            mid = m.get("id", "")
            likes = m.get("likes", 0)
            dl = m.get("downloads", 0)
            pipeline = m.get("pipeline_tag", "")
            title = f"[热门模型] {mid} · ❤️{likes} · 下载{dl}"
            content = (
                f"模型: {mid}\n类型: {pipeline}\nLikes: {likes} | 下载: {dl}\n"
                f"信号: HuggingFace 趋势榜，AI 圈正在关注/使用的新模型。\n"
                f"机会角度: 早接触新模型=早发现新能力和新应用机会。"
            )
            ok = insert_signal(
                conn, source_id=self._source_id, track=TRACK, signal_type="trending",
                title=title, content=content,
                url=f"https://huggingface.co/{mid}",
                metric_value=float(likes), metric_label="Likes",
                dedup_key=f"hfmodel:{mid}",
            )
            ins += ok
            skip += not ok
        return ins, skip


class HFTrendingSpaces(Collector):
    """HuggingFace 热门 Spaces：最热的 AI 应用/demo（可直接体验的产品）。"""
    name = "HuggingFace 热门应用"
    type = "api"
    track = TRACK
    layer = 1
    rating = 3
    TOP_N = 15

    def collect(self, conn) -> tuple[int, int]:
        with _client() as c:
            data = c.get(
                "https://huggingface.co/api/spaces?sort=trendingScore&limit=%d" % self.TOP_N
            ).json()
        ins = skip = 0
        for s in data:
            sid = s.get("id", "")
            likes = s.get("likes", 0)
            title = f"[热门AI应用] {sid} · ❤️{likes}"
            content = (
                f"应用: {sid}\nLikes: {likes}\n"
                f"信号: HuggingFace Spaces 趋势榜，最热的可直接体验的 AI 应用/demo。\n"
                f"机会角度: 热门 demo 反映用户需求，可借鉴/包装成产品或内容。"
            )
            ok = insert_signal(
                conn, source_id=self._source_id, track=TRACK, signal_type="trending",
                title=title, content=content,
                url=f"https://huggingface.co/spaces/{sid}",
                metric_value=float(likes), metric_label="Likes",
                dedup_key=f"hfspace:{sid}",
            )
            ins += ok
            skip += not ok
        return ins, skip


class HNTopAI(Collector):
    """HN Algolia：高分 AI 讨论（稳定替代失效的 HN-AI RSS）。"""
    name = "HN 高分AI讨论"
    type = "api"
    track = TRACK
    layer = 2
    rating = 2
    MIN_POINTS = 100
    TOP_N = 20

    def collect(self, conn) -> tuple[int, int]:
        url = (
            "https://hn.algolia.com/api/v1/search_by_date"
            f"?query=AI&tags=story&numericFilters=points%3E{self.MIN_POINTS}"
            f"&hitsPerPage={self.TOP_N}"
        )
        with _client() as c:
            data = c.get(url).json()
        ins = skip = 0
        for h in data.get("hits", []):
            title_text = h.get("title") or ""
            points = h.get("points", 0)
            ncomments = h.get("num_comments", 0)
            obj_id = h.get("objectID", "")
            link = h.get("url") or f"https://news.ycombinator.com/item?id={obj_id}"
            title = f"[HN热议] {title_text} · {points}pts"
            content = (
                f"{title_text}\nHN 得分: {points} | 评论: {ncomments}\n"
                f"讨论: https://news.ycombinator.com/item?id={obj_id}\n"
                f"信号: 技术圈正在热议的 AI 话题。"
            )
            ok = insert_signal(
                conn, source_id=self._source_id, track=TRACK, signal_type="news",
                title=title, content=content, url=link,
                metric_value=float(points), metric_label="HN得分",
                dedup_key=f"hnai:{obj_id}",
            )
            ins += ok
            skip += not ok
        return ins, skip


AI_COLLECTORS = [HFTrendingModels, HFTrendingSpaces, HNTopAI]
