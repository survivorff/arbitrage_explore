"""机会雷达 · 评估工作台（Streamlit）。

四个页面：
1. 📥 收件箱 —— 浏览待评估信号（按相关度排序），晋升为机会卡片
2. 🎯 机会卡片 —— 评估打分（六维框架）、编辑、发布
3. 📈 战绩追踪 —— 给已发布机会回填实际结果（信任资产）
4. 🛰️ 信息源 & 扫描 —— 管理源、一键扫描、数据概览

运行：streamlit run ui/app.py  （或 python radar.py ui）
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ENGINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE_DIR))

from db import init_db, session  # noqa: E402
from pipeline import scorer  # noqa: E402

st.set_page_config(page_title="机会雷达", page_icon="🛰️", layout="wide")
init_db()


# ---------------- 数据访问 ----------------
def fetch_signals(status: str, min_rel: float, limit: int) -> list[dict]:
    with session() as conn:
        rows = conn.execute(
            """SELECT s.*, src.name AS source_name, src.layer AS source_layer
               FROM signals s LEFT JOIN sources src ON s.source_id = src.id
               WHERE s.status = ? AND COALESCE(s.ai_relevance,0) >= ?
               ORDER BY s.ai_relevance DESC, s.fetched_at DESC
               LIMIT ?""",
            (status, min_rel, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def promote_signal(signal_id: int, title: str, summary: str) -> int:
    with session() as conn:
        cur = conn.execute(
            """INSERT INTO opportunities (signal_id, title, track, summary, status)
               VALUES (?, ?, ?, ?, 'draft')""",
            (signal_id, title, "AI工具", summary),
        )
        conn.execute("UPDATE signals SET status='promoted' WHERE id=?", (signal_id,))
        return cur.lastrowid


def set_signal_status(signal_id: int, status: str) -> None:
    with session() as conn:
        conn.execute("UPDATE signals SET status=? WHERE id=?", (status, signal_id))


def fetch_opportunities(status: str | None = None) -> list[dict]:
    with session() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM opportunities WHERE status=? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM opportunities ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def update_opportunity(opp_id: int, fields: dict) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [opp_id]
    with session() as conn:
        conn.execute(f"UPDATE opportunities SET {cols} WHERE id=?", vals)


def get_counts() -> dict:
    with session() as conn:
        def c(q, *a):
            return conn.execute(q, a).fetchone()[0]
        return {
            "sources": c("SELECT COUNT(*) FROM sources WHERE enabled=1"),
            "new": c("SELECT COUNT(*) FROM signals WHERE status='new'"),
            "high": c("SELECT COUNT(*) FROM signals WHERE status='new' AND COALESCE(ai_relevance,0)>=0.4"),
            "draft": c("SELECT COUNT(*) FROM opportunities WHERE status='draft'"),
            "published": c("SELECT COUNT(*) FROM opportunities WHERE status='published'"),
            "tracking": c("SELECT COUNT(*) FROM opportunities WHERE status IN ('published','tracking')"),
        }


# ---------------- 页面 ----------------
def page_inbox():
    st.header("📥 收件箱 · 待评估信号")
    st.caption("按相关度排序。机器做初筛，判断由你来做。点「晋升」把值得追踪的信号变成机会卡片。")

    col1, col2, col3 = st.columns(3)
    min_rel = col1.slider("最低相关度", 0.0, 1.0, 0.4, 0.1)
    limit = col2.selectbox("显示数量", [20, 50, 100], index=0)
    col3.metric("待评估信号", get_counts()["new"])

    signals = fetch_signals("new", min_rel, limit)
    if not signals:
        st.info("没有符合条件的待评估信号。去「信息源 & 扫描」跑一次扫描，或降低相关度阈值。")
        return

    for s in signals:
        rel = s.get("ai_relevance") or 0
        tags = s.get("ai_tags") or ""
        reason = s.get("ai_reason") or ""
        with st.container(border=True):
            top = st.columns([6, 1])
            top[0].markdown(f"**{s['raw_title']}**")
            top[1].markdown(f"`{rel:.2f}`")
            meta = f"来源: {s.get('source_name','?')} (L{s.get('source_layer','?')})"
            if tags:
                meta += f" · 标签: {tags}"
            if reason:
                meta += f" · AI: {reason}"
            st.caption(meta)
            if s.get("url"):
                st.caption(f"🔗 {s['url']}")

            with st.expander("摘要"):
                st.write((s.get("raw_content") or "")[:1000] or "（无摘要）")

            btns = st.columns([1, 1, 4])
            if btns[0].button("⬆️ 晋升为机会", key=f"promote_{s['id']}"):
                oid = promote_signal(s["id"], s["raw_title"], (s.get("raw_content") or "")[:200])
                st.success(f"已晋升为机会卡片 #{oid}，去「机会卡片」页评估。")
                st.rerun()
            if btns[1].button("🗑️ 过滤掉", key=f"drop_{s['id']}"):
                set_signal_status(s["id"], "filtered_out")
                st.rerun()


def _score_widget(label: str, desc: str, value: int, key: str) -> int:
    return st.slider(f"{label} · {desc}", 1, 5, max(1, int(value or 1)), key=key)


def page_opportunities():
    st.header("🎯 机会卡片 · 评估与编辑")
    st.caption("用知识库六维框架评估。注意：风险/合规得 1 分将触发一票否决。")

    drafts = fetch_opportunities("draft")
    if not drafts:
        st.info("暂无待评估的机会卡片。去「收件箱」晋升一些信号。")
        return

    titles = {f"#{o['id']} {o['title'][:40]}": o for o in drafts}
    picked = st.selectbox("选择要评估的机会", list(titles.keys()))
    o = titles[picked]

    with st.form(f"eval_{o['id']}"):
        st.subheader("基本信息")
        title = st.text_input("机会名称", o.get("title") or "")
        c1, c2 = st.columns(2)
        dimension = c1.selectbox(
            "套利维度", scorer.ARBITRAGE_DIMENSIONS,
            index=scorer.ARBITRAGE_DIMENSIONS.index(o["dimension"])
            if o.get("dimension") in scorer.ARBITRAGE_DIMENSIONS else 2,
        )
        half_life = c2.selectbox("时效/半衰期", scorer.HALF_LIFE_OPTIONS)
        summary = st.text_area("一句话是什么", o.get("summary") or "", height=68)
        why = st.text_area("为什么值得关注（价差/机会在哪）", o.get("why_matters") or "", height=80)
        risks = st.text_area("⚠️ 风险与坑（必填）", o.get("risks") or "", height=80)
        fit = st.text_input("适合谁 / 不适合谁", o.get("fit_for") or "")

        st.subheader("六维评估打分（1-5）")
        sc = {}
        cols = st.columns(2)
        for i, (field, name, weight, desc) in enumerate(scorer.DIMENSIONS):
            with cols[i % 2]:
                sc[field] = _score_widget(f"{name}(x{weight})", desc, o.get(field), f"{field}_{o['id']}")

        st.subheader("结论")
        c3, c4 = st.columns(2)
        judgment = c3.selectbox("我的判断", scorer.JUDGMENT_OPTIONS)
        disclosure = c4.text_input("利益披露", o.get("disclosure") or "无")
        judgment_reason = st.text_area("判断理由", o.get("judgment_reason") or "", height=68)

        submitted = st.form_submit_button("💾 保存评估")
        if submitted:
            fields = {
                "title": title, "dimension": dimension, "half_life": half_life,
                "summary": summary, "why_matters": why, "risks": risks, "fit_for": fit,
                "judgment": judgment, "judgment_reason": judgment_reason,
                "disclosure": disclosure, **sc,
            }
            update_opportunity(o["id"], fields)
            st.success("已保存。")

    # 实时显示框架结论
    current = {f: o.get(f, 1) for f, *_ in [(d[0],) for d in scorer.DIMENSIONS]}
    total = scorer.weighted_total({k: st.session_state.get(f"{k}_{o['id']}", current.get(k, 1)) for k in current})
    dec, why_dec = scorer.decision({k: st.session_state.get(f"{k}_{o['id']}", 1) for k in current})
    m = st.columns(3)
    m[0].metric("加权总分", f"{total}/{scorer.MAX_TOTAL}")
    m[1].metric("框架建议", dec)
    m[2].caption(why_dec)

    st.divider()
    cols = st.columns(3)
    if cols[0].button("✅ 标记为已发布", key=f"pub_{o['id']}"):
        update_opportunity(o["id"], {"status": "published", "published_at": _now()})
        st.success("已标记发布，进入战绩追踪。")
        st.rerun()
    if cols[1].button("🗑️ 丢弃此机会", key=f"discard_{o['id']}"):
        update_opportunity(o["id"], {"status": "discarded"})
        st.rerun()


def page_track():
    st.header("📈 战绩追踪 · 诚实记录")
    st.caption("给已发布机会回填实际结果。记录命中和看错——这是你最重要的信任资产。")

    opps = fetch_opportunities("published") + fetch_opportunities("tracking")
    if not opps:
        st.info("还没有已发布的机会。先在「机会卡片」里评估并发布。")
        return

    for o in opps:
        with st.container(border=True):
            st.markdown(f"**#{o['id']} {o['title']}**　· 判断: {o.get('judgment','-')} · 发布于 {o.get('published_at','-')}")
            c = st.columns([3, 1])
            outcome = c[0].text_input("实际结果", o.get("outcome") or "", key=f"out_{o['id']}")
            hit = c[1].selectbox(
                "命中?", ["未判定", "hit(命中)", "miss(看错)", "neutral(中性)"],
                key=f"hit_{o['id']}",
            )
            if st.button("保存", key=f"savetrack_{o['id']}"):
                hit_val = {"hit(命中)": "hit", "miss(看错)": "miss", "neutral(中性)": "neutral"}.get(hit)
                update_opportunity(o["id"], {
                    "outcome": outcome, "outcome_hit": hit_val, "status": "reviewed" if hit_val else "tracking",
                })
                st.success("已保存。")
                st.rerun()

    # 战绩汇总
    st.divider()
    with session() as conn:
        rows = conn.execute(
            "SELECT outcome_hit, COUNT(*) c FROM opportunities WHERE outcome_hit IS NOT NULL GROUP BY outcome_hit"
        ).fetchall()
    if rows:
        counts = {r["outcome_hit"]: r["c"] for r in rows}
        m = st.columns(3)
        m[0].metric("命中", counts.get("hit", 0))
        m[1].metric("看错", counts.get("miss", 0))
        m[2].metric("中性", counts.get("neutral", 0))
        st.caption("命中率仅供自我校准，绝不可用作'保证收益'的宣传（合规红线）。")


def page_sources():
    st.header("🛰️ 信息源 & 扫描")
    counts = get_counts()
    m = st.columns(4)
    m[0].metric("启用信息源", counts["sources"])
    m[1].metric("待评估信号", counts["new"])
    m[2].metric("高相关", counts["high"])
    m[3].metric("机会卡片(草稿)", counts["draft"])

    st.divider()
    st.subheader("一键扫描")
    st.caption("采集 RSS → 规则初筛 →（若配置）AI 打标。也可用命令行 `python radar.py scan`。")
    if st.button("🔄 立即扫描"):
        with st.spinner("采集中…"):
            from collectors.rss_collector import collect_all
            cs = collect_all()
        with st.spinner("规则初筛中…"):
            from pipeline.filter import run_rule_filter
            run_rule_filter(only_new=True)
        from config import config
        if config.ai_ready():
            with st.spinner("AI 打标中…"):
                from pipeline.ai_tagger import run_ai_tagger
                run_ai_tagger(limit=30)
        st.success(f"扫描完成：新增 {cs['inserted']} 条信号，{len(cs['errors'])} 个源失败。")
        st.rerun()

    st.divider()
    st.subheader("信息源清单")
    with session() as conn:
        rows = conn.execute(
            "SELECT name, type, layer, value_rating, last_fetched, enabled FROM sources ORDER BY layer, value_rating DESC"
        ).fetchall()
    st.dataframe([dict(r) for r in rows], use_container_width=True)
    st.caption("维护建议：往①②层（一手/社区）渗透，砍掉噪音源。见 build/03-信息源。")


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------- 导航 ----------------
PAGES = {
    "📥 收件箱": page_inbox,
    "🎯 机会卡片": page_opportunities,
    "📈 战绩追踪": page_track,
    "🛰️ 信息源 & 扫描": page_sources,
}

st.sidebar.title("🛰️ 机会雷达")
st.sidebar.caption("AI赛道机会的采集·评估·追踪工作台")
choice = st.sidebar.radio("导航", list(PAGES.keys()))
st.sidebar.divider()
_c = get_counts()
st.sidebar.metric("待评估", _c["new"])
st.sidebar.metric("草稿机会", _c["draft"])
st.sidebar.metric("已发布", _c["published"])

PAGES[choice]()
