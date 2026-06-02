"""开发者/开源赛道的 RSS 源（GitHub API 之外的 L2/L3 补充）。

GitHub Trending → 项目本身（已由 dev_collectors.GitHubRising 处理）
Reddit/HN → 社区讨论 → L3 评估素材
"""
from __future__ import annotations

from db import init_db, session

TRACK = "开发者开源"

SEED_RSS: list[tuple[str, str, int, int]] = [
    # ---- 社区/讨论（L3 评估素材）----
    ("Reddit r/programming", "https://www.reddit.com/r/programming/top/.rss?t=day", 2, 2),
    ("Reddit r/MachineLearning", "https://www.reddit.com/r/MachineLearning/top/.rss?t=day", 2, 2),
    ("Reddit r/LocalLLaMA", "https://www.reddit.com/r/LocalLLaMA/top/.rss?t=day", 2, 3),
    ("Reddit r/SideProject", "https://www.reddit.com/r/SideProject/top/.rss?t=day", 2, 2),
    # ---- 关键人物 / 优质技术博客 ----
    ("Simon Willison", "https://simonwillison.net/atom/everything/", 2, 3),
    # ---- HN ----
    ("HN: Show", "https://hnrss.org/show", 2, 2),
    ("HN: AI 高分", "https://hnrss.org/newest?q=AI&points=50", 2, 2),
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
    print(f"开发者赛道 RSS 源导入完成：新增 {inserted}，更新 {updated}。")


if __name__ == "__main__":
    seed()
