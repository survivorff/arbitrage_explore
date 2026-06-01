"""加密Web3 赛道的 RSS 资讯源（交易所公告类机会 + 行业资讯，作为 API 数据的补充）。

注意：加密赛道的核心机会来自 API 数据（见 collectors/crypto_collectors.py），
这里的 RSS 只是补充"新币上线/重大事件"类资讯。运行：python sources_seed_crypto.py
"""
from __future__ import annotations

from db import init_db, session

TRACK = "加密Web3"

# (name, url, layer, rating)
SEED_RSS: list[tuple[str, str, int, int]] = [
    ("Cointelegraph", "https://cointelegraph.com/rss", 3, 2),
    ("Decrypt", "https://decrypt.co/feed", 3, 2),
    ("The Block", "https://www.theblock.co/rss.xml", 3, 2),
    ("Bitcoin.com News", "https://news.bitcoin.com/feed/", 3, 2),
]


def seed() -> None:
    init_db()
    inserted, updated = 0, 0
    with session() as conn:
        for name, url, layer, rating in SEED_RSS:
            row = conn.execute("SELECT id FROM sources WHERE name = ?", (name,)).fetchone()
            if row:
                conn.execute(
                    "UPDATE sources SET type='rss', url=?, track=?, layer=?, value_rating=?, enabled=1 WHERE id=?",
                    (url, TRACK, layer, rating, row["id"]),
                )
                updated += 1
            else:
                conn.execute(
                    "INSERT INTO sources (name, type, url, track, layer, value_rating) VALUES (?, 'rss', ?, ?, ?, ?)",
                    (name, url, TRACK, layer, rating),
                )
                inserted += 1
    print(f"加密 RSS 源导入完成：新增 {inserted}，更新 {updated}。")


if __name__ == "__main__":
    seed()
