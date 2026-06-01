"""采集器基类与信号写入工具。

设计理念（回应"不同赛道数据源不同"）：
- 采集器分两类：
  1. 资讯类（RSS）—— 适合 AI工具、宏观新闻等"读文章"的赛道。
  2. 数据类（API）—— 适合加密Web3等"看数字机会"的赛道（APY、资金费率、新币）。
- 每个赛道在 tracks.py 里声明自己用哪些采集器。
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import session  # noqa: E402


def make_hash(*parts: str) -> str:
    key = "|".join(p or "" for p in parts)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def upsert_source(conn, name: str, type_: str, track: str, layer: int, rating: int) -> int:
    """确保某个采集器对应的 source 记录存在，返回 source_id。"""
    row = conn.execute("SELECT id FROM sources WHERE name = ?", (name,)).fetchone()
    if row:
        conn.execute(
            "UPDATE sources SET type=?, track=?, layer=?, value_rating=?, enabled=1 WHERE id=?",
            (type_, track, layer, rating, row["id"]),
        )
        return row["id"]
    cur = conn.execute(
        """INSERT INTO sources (name, type, url, track, layer, value_rating)
           VALUES (?, ?, '', ?, ?, ?)""",
        (name, type_, track, layer, rating),
    )
    return cur.lastrowid


def insert_signal(conn, *, source_id: int, track: str, signal_type: str,
                  title: str, content: str, url: str,
                  metric_value: float | None = None, metric_label: str | None = None,
                  published: str | None = None, dedup_key: str | None = None) -> bool:
    """写入一条信号（去重）。返回是否新增。"""
    h = make_hash(dedup_key or url, title)
    exists = conn.execute("SELECT 1 FROM signals WHERE hash = ?", (h,)).fetchone()
    if exists:
        return False
    conn.execute(
        """INSERT INTO signals
           (source_id, track, signal_type, raw_title, raw_content, url,
            metric_value, metric_label, hash, published)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (source_id, track, signal_type, title, content, url,
         metric_value, metric_label, h, published),
    )
    return True


class Collector:
    """采集器基类。子类实现 collect(conn) → (新增, 跳过)。"""

    name: str = "base"
    type: str = "api"        # rss / api
    track: str = ""
    layer: int = 3
    rating: int = 2

    def collect(self, conn) -> tuple[int, int]:
        raise NotImplementedError

    def run(self) -> tuple[int, int]:
        with session() as conn:
            sid = upsert_source(conn, self.name, self.type, self.track, self.layer, self.rating)
            self._source_id = sid
            ins, skip = self.collect(conn)
            conn.execute(
                "UPDATE sources SET last_fetched = datetime('now') WHERE id = ?", (sid,)
            )
        return ins, skip
