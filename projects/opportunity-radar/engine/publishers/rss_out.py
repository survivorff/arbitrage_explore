"""RSS 输出：把已发布的机会卡片生成标准 RSS feed.xml。

用户可用任意 RSS 阅读器订阅你的机会流——零摩擦、不依赖任何平台。
生成的 feed.xml 可托管到任意静态服务器/对象存储/GitHub Pages。
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import session  # noqa: E402

FEED_TITLE = "机会雷达 · Opportunity Radar"
FEED_DESC = "经过筛选与评估的机会情报（信息分享，不构成投资建议）"
FEED_LINK = "https://example.com/radar"   # 部署后替换为你的实际地址


def _published_opps(limit: int = 50, track: str | None = None) -> list[dict]:
    with session() as conn:
        sql = ("SELECT * FROM opportunities WHERE status IN ('published','tracking','reviewed')")
        params: list = []
        if track:
            sql += " AND track = ?"
            params.append(track)
        sql += " ORDER BY COALESCE(published_at, created_at) DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _item_xml(o: dict) -> str:
    title = escape(o.get("title") or "")
    desc_parts = []
    for label, key in [("是什么", "summary"), ("为什么", "why_matters"),
                       ("风险", "risks"), ("适合谁", "fit_for"),
                       ("判断", "judgment"), ("时效", "half_life")]:
        if o.get(key):
            desc_parts.append(f"{label}：{o[key]}")
    desc = escape(" | ".join(desc_parts))
    pub = o.get("published_at") or o.get("created_at") or ""
    guid = f"radar-opp-{o['id']}"
    return f"""    <item>
      <title>{title}</title>
      <description>{desc}</description>
      <category>{escape(o.get('track') or '')}</category>
      <guid isPermaLink="false">{guid}</guid>
      <pubDate>{escape(str(pub))}</pubDate>
    </item>"""


def build_feed(limit: int = 50, track: str | None = None) -> str:
    opps = _published_opps(limit, track)
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    items = "\n".join(_item_xml(o) for o in opps)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{escape(FEED_TITLE)}</title>
    <link>{escape(FEED_LINK)}</link>
    <description>{escape(FEED_DESC)}</description>
    <language>zh-cn</language>
    <lastBuildDate>{now}</lastBuildDate>
{items}
  </channel>
</rss>"""


def write_feed(path: str = "feed.xml", limit: int = 50, track: str | None = None) -> tuple[str, int]:
    """生成 feed.xml 到文件，返回 (路径, 条目数)。"""
    opps = _published_opps(limit, track)
    xml = build_feed(limit, track)
    out = Path(__file__).resolve().parent.parent / path
    out.write_text(xml, encoding="utf-8")
    return str(out), len(opps)


if __name__ == "__main__":
    p, n = write_feed()
    print(f"已生成 RSS feed：{p}（{n} 条机会）")
