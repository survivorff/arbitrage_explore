"""机会雷达引擎 · 统一命令行入口（按赛道）。

用法：
    python radar.py init                初始化数据库
    python radar.py tracks              列出所有赛道
    python radar.py setup <track>       初始化某赛道的数据源（crypto / ai）
    python radar.py scan <track>        采集+初筛某赛道（日常用这个）
    python radar.py stats               数据概览
    python radar.py health              数据源健康检查（定期跑，揪出失效源）
    python radar.py auto once [--push]  跑一轮自动采集+初筛（--push 推L4到Telegram）
    python radar.py auto loop --interval 3600 [--push]   定时循环
    python radar.py ui                  启动评估工作台（Streamlit）

示例（加密赛道走通全流程）：
    python radar.py init
    python radar.py setup crypto
    python radar.py scan crypto
    python radar.py ui
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE_DIR))

from db import init_db, session  # noqa: E402
from tracks import get_track, list_tracks  # noqa: E402


def cmd_init() -> None:
    init_db()
    print("✅ 数据库已初始化。")


def cmd_tracks() -> None:
    print("可用赛道：")
    for t in list_tracks():
        print(f"  {t.key:8} {t.name:10} — {t.desc}")


def cmd_setup(track_key: str) -> None:
    """初始化某赛道的数据源。"""
    init_db()
    if track_key == "ai":
        from sources_seed import seed
        seed()
    elif track_key == "crypto":
        from sources_seed_crypto import seed
        seed()
        print("加密赛道的 API 数据源（收益率/资金费率/趋势）无需预置，scan 时自动采集。")
    elif track_key == "dev":
        from sources_seed_dev import seed
        seed()
        print("开发者赛道的 GitHub API 数据源无需预置，scan 时自动采集。")
    else:
        print(f"未知赛道 {track_key}，可用：{[t.key for t in list_tracks()]}")
        return
    print(f"✅ 赛道 [{track_key}] 数据源已就绪。")


def _scan_track(track_key: str) -> None:
    track = get_track(track_key)
    if not track:
        print(f"未知赛道 {track_key}，可用：{[t.key for t in list_tracks()]}")
        return
    print(f"🛰️ 扫描赛道：{track.name}")
    total_ins = 0

    # 1. API 数据采集器（加密赛道的核心）
    for cls in track.api_collectors:
        col = cls()
        try:
            i, s = col.run()
            total_ins += i
            print(f"  [API] {col.name}: 新增 {i}，跳过 {s}")
        except Exception as e:
            print(f"  [API] {col.name} 失败: {e}")

    # 2. RSS 资讯源（按赛道过滤）
    if track.rss_track:
        from collectors.rss_collector import collect_all
        rss = collect_all(track=track.rss_track)
        total_ins += rss["inserted"]
        print(f"  [RSS] {rss['sources']} 源 / 新增 {rss['inserted']} / 失败 {len(rss['errors'])}")

    # 3. 规则初筛
    from pipeline.filter import run_rule_filter
    f = run_rule_filter(only_new=True, track=track.name)
    print(f"  [初筛] 处理 {f['processed']} | L4 {f.get('L4',0)} L3 {f.get('L3',0)} L2 {f.get('L2',0)} L1 {f.get('L1',0)} ⚠️骗局 {f.get('scam',0)}")

    # 4. AI 打标（可选）
    from config import config
    if config.ai_ready():
        from pipeline.ai_tagger import run_ai_tagger
        run_ai_tagger(limit=30)

    print(f"\n🎯 扫描完成，本次新增 {total_ins} 条信号。运行 `python radar.py ui` 进入工作台。")


def cmd_scan(track_key: str | None) -> None:
    if not track_key:
        print("请指定赛道：python radar.py scan crypto|ai")
        return
    _scan_track(track_key)


def cmd_stats() -> None:
    with session() as conn:
        def c(q, *a):
            return conn.execute(q, a).fetchone()[0]
        print("📊 机会雷达数据概览")
        print(f"  启用信息源:   {c('SELECT COUNT(*) FROM sources WHERE enabled=1')}")
        print(f"  信号总数:     {c('SELECT COUNT(*) FROM signals')}")
        new_count = c("SELECT COUNT(*) FROM signals WHERE status='new'")
        print(f"  待评估信号:   {new_count}")
        # 按赛道
        rows = conn.execute(
            "SELECT track, COUNT(*) n FROM signals WHERE status='new' GROUP BY track"
        ).fetchall()
        for r in rows:
            print(f"     - {r['track'] or '(无赛道)'}: {r['n']}")
        print(f"  机会卡片:     {c('SELECT COUNT(*) FROM opportunities')}")


def cmd_health() -> None:
    from pipeline.health import run_health_check, print_report
    print_report(run_health_check(disable_dead=False))


def cmd_auto(arg: str | None) -> None:
    """定时自动化：透传给 scheduler。arg 为 'once'/'loop' 等，默认 once。"""
    import subprocess
    sched = ENGINE_DIR / "scheduler.py"
    rest = sys.argv[2:] if len(sys.argv) > 2 else ["once"]
    subprocess.run([sys.executable, str(sched)] + rest, check=False)


def cmd_ui() -> None:
    app = ENGINE_DIR / "ui" / "app.py"
    print("启动评估工作台（Ctrl+C 退出）…")
    subprocess.run(["streamlit", "run", str(app)], check=False)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    dispatch = {
        "init": lambda: cmd_init(),
        "tracks": lambda: cmd_tracks(),
        "setup": lambda: cmd_setup(arg) if arg else print("请指定赛道：setup crypto|ai"),
        "scan": lambda: cmd_scan(arg),
        "stats": lambda: cmd_stats(),
        "health": lambda: cmd_health(),
        "auto": lambda: cmd_auto(arg),
        "ui": lambda: cmd_ui(),
    }
    if cmd not in dispatch:
        print(__doc__)
        return
    dispatch[cmd]()


if __name__ == "__main__":
    main()
