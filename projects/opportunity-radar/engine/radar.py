"""机会雷达引擎 · 统一命令行入口。

用法：
    python radar.py init        初始化数据库
    python radar.py seed        导入种子信息源
    python radar.py collect     采集所有 RSS 源到收件箱
    python radar.py filter      规则初筛（给信号打相关度）
    python radar.py ai          AI 初筛打标（需配置 AI）
    python radar.py scan        一键：collect + filter + ai（日常用这个）
    python radar.py stats       查看当前数据概览
    python radar.py ui          启动评估工作台（Streamlit）
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE_DIR))

from db import init_db, session  # noqa: E402


def cmd_init() -> None:
    init_db()
    print("✅ 数据库已初始化。")


def cmd_seed() -> None:
    from sources_seed import seed
    seed()


def cmd_collect() -> None:
    from collectors.rss_collector import collect_all
    print("开始采集 RSS…")
    s = collect_all()
    print(f"✅ 采集完成：{s['sources']} 源 / 新增 {s['inserted']} / 跳过 {s['skipped']} / 失败 {len(s['errors'])}")


def cmd_filter() -> None:
    from pipeline.filter import run_rule_filter
    st = run_rule_filter(only_new=True)
    print(f"✅ 规则初筛：处理 {st['processed']} / 高相关 {st['high']} / 低相关 {st['low']}")


def cmd_ai() -> None:
    from pipeline.ai_tagger import run_ai_tagger
    st = run_ai_tagger(limit=30, min_rule_score=0.0)
    if not st.get("skipped_ai"):
        print(f"✅ AI 打标：处理 {st['processed']} 条")


def cmd_scan() -> None:
    """日常一键流程。"""
    cmd_collect()
    cmd_filter()
    cmd_ai()
    print("\n🎯 扫描完成。运行 `python radar.py ui` 进入评估工作台。")


def cmd_stats() -> None:
    with session() as conn:
        sources = conn.execute("SELECT COUNT(*) c FROM sources WHERE enabled=1").fetchone()["c"]
        sig_total = conn.execute("SELECT COUNT(*) c FROM signals").fetchone()["c"]
        sig_new = conn.execute("SELECT COUNT(*) c FROM signals WHERE status='new'").fetchone()["c"]
        sig_high = conn.execute(
            "SELECT COUNT(*) c FROM signals WHERE status='new' AND COALESCE(ai_relevance,0)>=0.4"
        ).fetchone()["c"]
        opp = conn.execute("SELECT COUNT(*) c FROM opportunities").fetchone()["c"]
        opp_pub = conn.execute(
            "SELECT COUNT(*) c FROM opportunities WHERE status='published'"
        ).fetchone()["c"]
    print("📊 机会雷达数据概览")
    print(f"  启用信息源:   {sources}")
    print(f"  信号总数:     {sig_total}")
    print(f"  待评估信号:   {sig_new}（其中高相关 {sig_high}）")
    print(f"  机会卡片:     {opp}（已发布 {opp_pub}）")


def cmd_ui() -> None:
    app = ENGINE_DIR / "ui" / "app.py"
    print("启动评估工作台（Ctrl+C 退出）…")
    subprocess.run(["streamlit", "run", str(app)], check=False)


COMMANDS = {
    "init": cmd_init,
    "seed": cmd_seed,
    "collect": cmd_collect,
    "filter": cmd_filter,
    "ai": cmd_ai,
    "scan": cmd_scan,
    "stats": cmd_stats,
    "ui": cmd_ui,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(0 if len(sys.argv) < 2 else 1)
    COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    main()
