"""RSS 采集器：拉取启用的 RSS 源 → 去重 → 写入 signals 收件箱。

礼貌抓取：带 User-Agent、设超时。失败的源不影响其他源。
"""
from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import feedparser

# 允许从子目录直接运行（把 engine 根目录加入路径）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import config  # noqa: E402
from db import session  # noqa: E402


def _make_hash(url: str, title: str) -> str:
    """用 url + 标题生成去重指纹。"""
    key = (url or "") + "|" + (title or "")
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _entry_content(entry) -> str:
    """从 feed entry 中提取正文/摘要。"""
    for attr in ("summary", "description"):
        val = getattr(entry, attr, None)
        if val:
            return str(val)
    content = getattr(entry, "content", None)
    if content and isinstance(content, list) and content:
        return str(content[0].get("value", ""))
    return ""


def _published(entry) -> str | None:
    for attr in ("published", "updated"):
        val = getattr(entry, attr, None)
        if val:
            return str(val)
    return None


def collect_one(conn, source: dict) -> tuple[int, int]:
    """采集单个源，返回 (新增, 跳过)。"""
    parsed = feedparser.parse(
        source["url"],
        request_headers={"User-Agent": config.USER_AGENT},
    )
    inserted, skipped = 0, 0
    entries = parsed.entries[: config.FETCH_LIMIT]
    for entry in entries:
        title = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", "").strip()
        if not title and not link:
            continue
        h = _make_hash(link, title)
        exists = conn.execute("SELECT 1 FROM signals WHERE hash = ?", (h,)).fetchone()
        if exists:
            skipped += 1
            continue
        conn.execute(
            """INSERT INTO signals (source_id, raw_title, raw_content, url, hash, published)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source["id"], title, _entry_content(entry), link, h, _published(entry)),
        )
        inserted += 1
    # 更新源的最后采集时间
    conn.execute(
        "UPDATE sources SET last_fetched = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(timespec="seconds"), source["id"]),
    )
    return inserted, skipped


def collect_all() -> dict:
    """采集所有启用的 RSS 源。"""
    stats = {"sources": 0, "inserted": 0, "skipped": 0, "errors": []}
    with session() as conn:
        rows = conn.execute(
            "SELECT * FROM sources WHERE enabled = 1 AND type = 'rss'"
        ).fetchall()
        for row in rows:
            source = dict(row)
            stats["sources"] += 1
            try:
                ins, skip = collect_one(conn, source)
                stats["inserted"] += ins
                stats["skipped"] += skip
                print(f"  [{source['name']}] 新增 {ins}，跳过 {skip}")
            except Exception as e:  # 单源失败不影响整体
                msg = f"{source['name']}: {e}"
                stats["errors"].append(msg)
                print(f"  [WARN] 采集失败 {msg}")
    return stats


if __name__ == "__main__":
    print("开始 RSS 采集…")
    s = collect_all()
    print(
        f"\n完成：{s['sources']} 个源，新增 {s['inserted']} 条，"
        f"跳过 {s['skipped']} 条，失败 {len(s['errors'])} 个源。"
    )
