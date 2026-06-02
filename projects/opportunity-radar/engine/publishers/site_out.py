"""公开页生成：把已发布机会渲染成一个静态 HTML 页面（用户自助浏览 + 订阅入口）。

零部署：生成的 site/index.html 可托管到 GitHub Pages / 对象存储 / 任意静态空间。
页面含：按赛道分组的机会列表 + 各赛道 RSS 订阅链接 + Telegram 入口（可配）。
这是"阶段C 公开订阅页"的轻量起点（先静态，后续可做动态自助订阅）。
"""
from __future__ import annotations

import os
import sys
from datetime import date
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import session  # noqa: E402

LEVEL_BADGE = {4: ("🟢 L4 即时可行动", "#16a34a"), 3: ("🟡 L3 待评估", "#ca8a04"),
               2: ("🔵 L2 背景", "#2563eb"), 1: ("🔴 L1", "#dc2626"), 0: ("⚪", "#888")}


def _published(track: str | None = None) -> list[dict]:
    with session() as conn:
        sql = "SELECT * FROM opportunities WHERE status IN ('published','tracking','reviewed')"
        params: list = []
        if track:
            sql += " AND track=?"
            params.append(track)
        sql += " ORDER BY COALESCE(published_at,created_at) DESC"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _card_html(o: dict) -> str:
    badge_text, color = LEVEL_BADGE.get(0, ("", "#888"))
    parts = [f'<div class="card">']
    parts.append(f'<h3>{escape(o.get("title") or "")}</h3>')
    parts.append(f'<div class="meta">赛道：{escape(o.get("track") or "-")} · '
                 f'维度：{escape(o.get("dimension") or "-")} · 判断：{escape(o.get("judgment") or "-")}</div>')
    if o.get("summary"):
        parts.append(f'<p>{escape(o["summary"])}</p>')
    if o.get("why_matters"):
        parts.append(f'<p><b>为什么值得关注：</b>{escape(o["why_matters"])}</p>')
    if o.get("risks"):
        parts.append(f'<p class="risk"><b>⚠️ 风险：</b>{escape(o["risks"])}</p>')
    if o.get("fit_for"):
        parts.append(f'<p><b>适合谁：</b>{escape(o["fit_for"])}</p>')
    parts.append("</div>")
    return "\n".join(parts)


def build_site(tg_channel: str = "") -> str:
    opps = _published()
    by_track: dict[str, list] = {}
    for o in opps:
        by_track.setdefault(o.get("track") or "其他", []).append(o)

    sub_links = []
    for track in by_track:
        sub_links.append(f'<li>{escape(track)}：<code>feed.xml</code>（RSS 订阅）</li>')
    tg_html = (f'<p>📲 Telegram 频道：<a href="https://t.me/{escape(tg_channel.lstrip("@"))}">'
               f'{escape(tg_channel)}</a></p>') if tg_channel else ""

    sections = []
    for track, items in by_track.items():
        cards = "\n".join(_card_html(o) for o in items)
        sections.append(f'<section><h2>{escape(track)}（{len(items)}）</h2>{cards}</section>')

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>机会雷达 · 精选机会</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 760px;
         margin: 0 auto; padding: 20px; color: #1a1a1a; line-height: 1.6; }}
  h1 {{ font-size: 24px; }}
  h2 {{ margin-top: 32px; border-bottom: 2px solid #eee; padding-bottom: 6px; }}
  .card {{ border: 1px solid #e5e5e5; border-radius: 10px; padding: 14px 16px;
           margin: 12px 0; background: #fafafa; }}
  .card h3 {{ margin: 0 0 6px; font-size: 16px; }}
  .meta {{ color: #666; font-size: 13px; margin-bottom: 8px; }}
  .risk {{ color: #b45309; }}
  .sub {{ background: #f0f7ff; border-radius: 10px; padding: 12px 16px; margin: 16px 0; }}
  .disclaimer {{ color: #999; font-size: 12px; margin-top: 32px; border-top: 1px solid #eee; padding-top: 12px; }}
  code {{ background: #eee; padding: 2px 6px; border-radius: 4px; }}
</style>
</head>
<body>
<h1>🛰️ 机会雷达 · 精选机会</h1>
<p>经过筛选与评估的机会情报。更新于 {date.today().isoformat()}。</p>
<div class="sub">
  <b>📬 订阅方式</b>
  <ul>{''.join(sub_links)}</ul>
  {tg_html}
</div>
{''.join(sections) if sections else '<p>暂无已发布机会。</p>'}
<div class="disclaimer">
  免责声明：本页内容仅为信息分享与研究交流，不构成任何投资、财务或法律建议，
  不构成买卖推荐。信息可能有误或延迟，请自行核实、独立决策、自负风险。
</div>
</body>
</html>"""


def write_site(path: str = "site/index.html") -> tuple[str, int]:
    opps = _published()
    tg = os.environ.get("RADAR_TG_CHANNEL", "")
    html = build_site(tg_channel=tg)
    out = Path(__file__).resolve().parent.parent / path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return str(out), len(opps)


if __name__ == "__main__":
    p, n = write_site()
    print(f"已生成公开页：{p}（{n} 条机会）")
