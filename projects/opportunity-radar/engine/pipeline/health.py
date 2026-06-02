"""数据源健康检查：探测每个信息源是否还活着，防止源悄悄失效。

回应"持续检查数据源"。对每个 RSS / API 源做轻量探测：
- RSS：能否解析出条目。
- API 采集器：能否成功返回数据。

输出健康报告，并把连续失败的源标记/停用（可选）。建议定期跑（如每周）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import feedparser

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import config  # noqa: E402
from db import session  # noqa: E402


def check_rss(url: str, name: str = "") -> tuple[bool, str]:
    """探测一个 RSS 源。返回 (是否健康, 说明)。"""
    ua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
          if "reddit" in name.lower() else config.USER_AGENT)
    try:
        d = feedparser.parse(url, request_headers={"User-Agent": ua})
        n = len(d.entries)
        status = getattr(d, "status", None)
        if n > 0:
            return True, f"OK · {n} 条 · HTTP {status}"
        if status and status >= 400:
            return False, f"HTTP {status} · 0 条"
        return False, f"0 条 (HTTP {status}) · 可能失效或需JS渲染"
    except Exception as e:
        return False, f"异常: {e}"


def check_api_collectors() -> list[dict]:
    """探测各赛道的 API 采集器（不写库，只测连通）。"""
    from tracks import list_tracks
    results = []
    for track in list_tracks():
        for cls in track.api_collectors:
            col = cls()
            try:
                # 用一个临时内存连接测试 collect 是否能跑（不落库）
                import sqlite3
                tmp = sqlite3.connect(":memory:")
                tmp.row_factory = sqlite3.Row
                from db import SCHEMA
                tmp.executescript(SCHEMA)
                tmp.execute(
                    "INSERT INTO sources (id, name, type) VALUES (1, ?, 'api')",
                    (col.name,),
                )
                col._source_id = 1
                ins, skip = col.collect(tmp)
                tmp.close()
                results.append({"name": col.name, "type": "api", "track": track.name,
                                "healthy": ins + skip > 0,
                                "detail": f"OK · 取到 {ins + skip} 条"})
            except Exception as e:
                results.append({"name": col.name, "type": "api", "track": track.name,
                                "healthy": False, "detail": f"异常: {e}"})
    return results


def run_health_check(disable_dead: bool = False) -> dict:
    """全量健康检查。disable_dead=True 时停用探测失败的 RSS 源。"""
    report = {"rss": [], "api": [], "healthy": 0, "dead": 0}

    # RSS 源
    with session() as conn:
        rows = conn.execute(
            "SELECT id, name, url, track FROM sources WHERE enabled=1 AND type='rss'"
        ).fetchall()
        sources = [dict(r) for r in rows]

    for s in sources:
        ok, detail = check_rss(s["url"], s["name"])
        report["rss"].append({"name": s["name"], "track": s["track"],
                              "healthy": ok, "detail": detail})
        if ok:
            report["healthy"] += 1
        else:
            report["dead"] += 1
            if disable_dead:
                with session() as conn:
                    conn.execute("UPDATE sources SET enabled=0 WHERE id=?", (s["id"],))

    # API 采集器
    api_results = check_api_collectors()
    report["api"] = api_results
    for r in api_results:
        if r["healthy"]:
            report["healthy"] += 1
        else:
            report["dead"] += 1

    return report


def print_report(report: dict) -> None:
    print("=" * 60)
    print("🩺 数据源健康检查报告")
    print("=" * 60)
    print("\n【API 采集器】")
    for r in report["api"]:
        icon = "✅" if r["healthy"] else "❌"
        print(f"  {icon} [{r['track']}] {r['name']}: {r['detail']}")
    print("\n【RSS 源】")
    # 按赛道分组
    by_track: dict[str, list] = {}
    for r in report["rss"]:
        by_track.setdefault(r["track"] or "(无)", []).append(r)
    for track, items in by_track.items():
        print(f"  ◆ {track}")
        for r in items:
            icon = "✅" if r["healthy"] else "❌"
            print(f"    {icon} {r['name']}: {r['detail']}")
    print("\n" + "-" * 60)
    print(f"健康: {report['healthy']} · 失效: {report['dead']}")
    if report["dead"]:
        print("⚠️ 有源失效。修复方法：更新 sources_seed*.py 里的 URL，或 setup 重新导入。")


if __name__ == "__main__":
    rpt = run_health_check(disable_dead=False)
    print_report(rpt)
