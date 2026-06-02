"""定时自动化：无人值守地跑 采集→初筛，并可选自动推送高等级机会。

用法：
    python scheduler.py once           跑一轮所有赛道（采集+初筛），不推送
    python scheduler.py once --push     跑一轮并把"新出现的 L4 机会"推送到 Telegram
    python scheduler.py loop --interval 3600   每 3600 秒循环跑一轮
    python scheduler.py loop --interval 3600 --push

设计：
- 只用标准库 + 现有模块，无需额外依赖（不引入 APScheduler，保持轻量）。
- "自动推送"只推 L4（即时可行动）且非骗局的**新**信号，避免刷屏。
- 自动推送的是"原始高价值信号"，作为提醒；正式对外内容仍建议人工评估后用分发中心发。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE_DIR))

from db import init_db, session  # noqa: E402
from tracks import list_tracks  # noqa: E402


def run_once(push: bool = False) -> dict:
    """跑一轮：所有赛道采集+初筛。push=True 时推送新 L4 信号到 Telegram。"""
    init_db()
    summary = {"tracks": 0, "new_signals": 0, "pushed": 0}

    # 记录推送前已存在的信号 id 最大值，用于识别"本轮新增"
    with session() as conn:
        before_max = conn.execute("SELECT COALESCE(MAX(id),0) m FROM signals").fetchone()["m"]

    for track in list_tracks():
        summary["tracks"] += 1
        # API 采集器
        for cls in track.api_collectors:
            try:
                cls().run()
            except Exception as e:
                print(f"  [warn] {cls.__name__}: {e}")
        # RSS
        if track.rss_track:
            try:
                from collectors.rss_collector import collect_all
                collect_all(track=track.rss_track)
            except Exception as e:
                print(f"  [warn] RSS {track.name}: {e}")
        # 初筛
        from pipeline.filter import run_rule_filter
        run_rule_filter(only_new=True, track=track.name)

    with session() as conn:
        new_count = conn.execute(
            "SELECT COUNT(*) c FROM signals WHERE id > ?", (before_max,)
        ).fetchone()["c"]
    summary["new_signals"] = new_count

    if push:
        summary["pushed"] = _push_new_l4(before_max)

    return summary


def _push_new_l4(after_id: int, max_push: int = 10) -> int:
    """把本轮新增、L4、非骗局的信号推送到 Telegram。"""
    from publishers.telegram_pub import tg_ready, send_message
    if not tg_ready():
        print("  [push] Telegram 未配置，跳过推送。")
        return 0
    with session() as conn:
        rows = conn.execute(
            """SELECT * FROM signals
               WHERE id > ? AND level = 4 AND COALESCE(scam_flag,0) = 0 AND status='new'
               ORDER BY ai_relevance DESC LIMIT ?""",
            (after_id, max_push),
        ).fetchall()
        signals = [dict(r) for r in rows]
    pushed = 0
    for s in signals:
        text = _format_signal(s)
        ok, _ = send_message(text)
        if ok:
            pushed += 1
        time.sleep(0.5)  # 避免触发限流
    return pushed


def _format_signal(s: dict) -> str:
    """把原始高价值信号格式化为提醒消息。"""
    lines = [f"🟢 *L4 新机会* · {s.get('track','')}", "", s.get("raw_title", "")]
    if s.get("metric_value") is not None and s.get("metric_label"):
        lines.append(f"📊 {s['metric_label']}: {s['metric_value']:.2f}")
    if s.get("url"):
        lines.append(s["url"])
    lines.append("")
    lines.append("_自动提醒 · 仅信息分享不构成投资建议 · 人工评估后再行动_")
    return "\n".join(lines)


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] not in ("once", "loop"):
        print(__doc__)
        return
    push = "--push" in args
    if args[0] == "once":
        s = run_once(push=push)
        print(f"✅ 完成一轮：{s['tracks']} 赛道 / 新增 {s['new_signals']} 信号 / 推送 {s['pushed']}")
        return
    # loop
    interval = 3600
    if "--interval" in args:
        try:
            interval = int(args[args.index("--interval") + 1])
        except (ValueError, IndexError):
            pass
    print(f"🔁 循环模式：每 {interval} 秒跑一轮（Ctrl+C 退出）。推送={push}")
    try:
        while True:
            s = run_once(push=push)
            print(f"  [{time.strftime('%H:%M:%S')}] 新增 {s['new_signals']} / 推送 {s['pushed']}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n已停止。")


if __name__ == "__main__":
    main()
