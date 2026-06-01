"""初始信息源种子：AI 赛道的一批 RSS 源。

按知识库信息源分层标注 layer（1=一手 … 5=大众）。
运行：python sources_seed.py  → 幂等导入（按 url 去重）。

⚠️ 这是起步清单，需要你在使用中持续维护：
   - 砍掉噪音源、补充①②层一手源（见 build/03-信息源 与概念篇）。
   - RSS 地址可能变动，失效的请更新。
"""
from __future__ import annotations

from db import init_db, session

# (name, type, url, layer, value_rating)
# layer: 1一手 2社区 3媒体 4聚合 5大众
SEED_SOURCES: list[tuple[str, str, str, int, int]] = [
    # ---- 官方/接近一手（厂商博客、研究）----
    ("OpenAI News", "rss", "https://openai.com/news/rss.xml", 1, 3),
    ("Google AI Blog", "rss", "https://blog.google/technology/ai/rss/", 1, 3),
    ("Hugging Face Blog", "rss", "https://huggingface.co/blog/feed.xml", 1, 3),
    ("DeepMind Blog", "rss", "https://deepmind.google/blog/rss.xml", 1, 3),
    # ---- 社区/产品发现（新工具首发地）----
    ("Hacker News (front)", "rss", "https://hnrss.org/frontpage", 2, 2),
    ("Hacker News: AI", "rss", "https://hnrss.org/newest?q=AI&points=50", 2, 2),
    ("Product Hunt", "rss", "https://www.producthunt.com/feed", 2, 2),
    # ---- 关键人物 / 优质分析（接近一手的判断）----
    ("Simon Willison", "rss", "https://simonwillison.net/atom/everything/", 2, 3),
    ("Latent Space", "rss", "https://www.latent.space/feed", 3, 3),
    # ---- 垂直媒体（已加工，补理解层）----
    ("TechCrunch AI", "rss", "https://techcrunch.com/category/artificial-intelligence/feed/", 3, 2),
    ("VentureBeat AI", "rss", "https://venturebeat.com/category/ai/feed/", 3, 2),
    ("The Verge AI", "rss", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", 3, 2),
    ("MIT Tech Review", "rss", "https://www.technologyreview.com/feed/", 3, 2),
    # ---- 中文媒体（国内赛道贴近受众）----
    ("量子位", "rss", "https://www.qbitai.com/feed", 3, 3),
    ("36氪", "rss", "https://36kr.com/feed", 3, 2),
    ("InfoQ中文", "rss", "https://www.infoq.cn/feed", 3, 2),
    ("阮一峰周刊", "rss", "https://feeds.feedburner.com/ruanyifeng", 3, 2),
]


def seed() -> None:
    init_db()
    inserted, updated = 0, 0
    seed_names = {name for name, *_ in SEED_SOURCES}
    with session() as conn:
        for name, type_, url, layer, rating in SEED_SOURCES:
            row = conn.execute("SELECT id FROM sources WHERE name = ?", (name,)).fetchone()
            if row:
                # 更新已有源（修正 URL/层级/评级，并确保启用）
                conn.execute(
                    """UPDATE sources SET type=?, url=?, track=?, layer=?, value_rating=?, enabled=1
                       WHERE id=?""",
                    (type_, url, "AI工具", layer, rating, row["id"]),
                )
                updated += 1
            else:
                conn.execute(
                    """INSERT INTO sources (name, type, url, track, layer, value_rating)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (name, type_, url, "AI工具", layer, rating),
                )
                inserted += 1
        # 停用已从种子清单移除的旧源（如失效的机器之心），不删除以保留历史
        rows = conn.execute("SELECT id, name FROM sources").fetchall()
        disabled = 0
        for r in rows:
            if r["name"] not in seed_names:
                conn.execute("UPDATE sources SET enabled=0 WHERE id=?", (r["id"],))
                disabled += 1
    print(f"种子源导入完成：新增 {inserted}，更新 {updated}，停用旧源 {disabled}。")


if __name__ == "__main__":
    seed()
