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
def fetch_signals(status: str, min_rel: float, limit: int,
                  keyword: str = "", source_id: int | None = None,
                  track: str | None = None, level: int | None = None) -> list[dict]:
    sql = (
        "SELECT s.*, src.name AS source_name, src.layer AS source_layer "
        "FROM signals s LEFT JOIN sources src ON s.source_id = src.id "
        "WHERE s.status = ? AND COALESCE(s.ai_relevance,0) >= ?"
    )
    params: list = [status, min_rel]
    if track:
        sql += " AND s.track = ?"
        params.append(track)
    if level is not None:
        sql += " AND COALESCE(s.level,0) = ?"
        params.append(level)
    if keyword:
        sql += " AND (s.raw_title LIKE ? OR s.raw_content LIKE ?)"
        params += [f"%{keyword}%", f"%{keyword}%"]
    if source_id:
        sql += " AND s.source_id = ?"
        params.append(source_id)
    # 排序：等级降序（L4 优先）→ 相关度降序 → 时间倒序
    sql += " ORDER BY COALESCE(s.level,0) DESC, s.ai_relevance DESC, s.fetched_at DESC LIMIT ?"
    params.append(limit)
    with session() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def list_tracks_in_db() -> list[str]:
    with session() as conn:
        rows = conn.execute(
            "SELECT DISTINCT track FROM signals WHERE track IS NOT NULL AND track != '' ORDER BY track"
        ).fetchall()
        return [r["track"] for r in rows]


def list_sources() -> list[dict]:
    with session() as conn:
        rows = conn.execute(
            "SELECT id, name FROM sources WHERE enabled=1 ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]


def promote_signal(signal_id: int, title: str, summary: str) -> int:
    with session() as conn:
        # 继承信号的真实赛道与维度线索，不再硬编码
        sig = conn.execute(
            "SELECT track, signal_type FROM signals WHERE id=?", (signal_id,)
        ).fetchone()
        track = (sig["track"] if sig and sig["track"] else "") or ""
        cur = conn.execute(
            """INSERT INTO opportunities (signal_id, title, track, summary, status)
               VALUES (?, ?, ?, ?, 'draft')""",
            (signal_id, title, track, summary),
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
            "L4": c("SELECT COUNT(*) FROM signals WHERE status='new' AND level=4"),
            "L3": c("SELECT COUNT(*) FROM signals WHERE status='new' AND level=3"),
            "scam": c("SELECT COUNT(*) FROM signals WHERE status='new' AND scam_flag=1"),
            "draft": c("SELECT COUNT(*) FROM opportunities WHERE status='draft'"),
            "published": c("SELECT COUNT(*) FROM opportunities WHERE status='published'"),
            "tracking": c("SELECT COUNT(*) FROM opportunities WHERE status IN ('published','tracking')"),
        }


# ---------------- 页面 ----------------
def page_guide():
    st.header("🏁 使用引导 · 5 分钟看懂怎么用")
    st.markdown("""
### 这个工具是做什么的？

**一句话**：它帮你把"散落在各处的原始信号"加工成"可行动的机会判断"，本质是**信息差套利**——
你比别人更早、更准地发现机会，省下他们的信息采集时间，这就是价值。

```
数据源 → [机器]采集+初筛 → 📥收件箱 → [你]评估判断 → 🎯机会卡片 → 📰简报 → 发布给受众
         机器干脏活累活            你只做最有价值的"判断"            变现
```

---

### 完整流程（照着走一遍就懂了）

**第 1 步 · 🛰️ 信息源 & 扫描** → 选一个赛道（如"加密Web3"），点「立即扫描」。
机器会从数据源拉取信号（加密赛道拉的是**真实的收益率/资金费率/趋势数据**，不是新闻）。

**第 2 步 · 📥 收件箱** → 浏览机器筛好的信号（按相关度排序）。
看到值得做成机会的，点「⬆️晋升」；没用的点「🗑️过滤」。**这一步是你的核心工作。**

**第 3 步 · 🎯 机会卡片** → 给晋升的机会用"六维框架"打分，写下判断、风险、适合谁。
这是你和"纯搬运信息的人"的本质区别——**你给的是判断，不是转发。**

**第 4 步 · 📰 简报生成** → 勾选评估好的机会，一键导出 Markdown 简报。
人工润色后发到公众号/小红书/社群。

**第 5 步 · 📈 战绩追踪** → 过段时间回来记录"这个机会后来怎么样了"（含看错的）。
诚实的战绩记录 = 你最重要的信任资产。

---

### 为什么不同赛道数据源不同？

- **加密Web3**：机会是"带数字的量化信号"——DeFi 收益率(APY)、资金费率、趋势币。
  来自**链上数据 API**（DeFiLlama / Binance / CoinGecko），不是新闻 RSS。
- **AI工具**：机会主要以"文章/发布"形式出现，来自厂商博客、社区、媒体的 **RSS**。

> 这就是为什么收件箱里加密信号会显示 **📊 APY / 资金费率** 这样的关键数字。

---

### 机会分四级（收件箱按等级排序，L4 最优先）

| 等级 | 含义 | 例子 |
|------|------|------|
| 🟢 **L4** | 即时可行动 | 合理高息池(10-50% APY)、新晋爆款开源项目、限免红利 |
| 🟡 **L3** | 待评估（需研究） | 高息但要看可持续性、新公链空投 |
| 🔵 **L2** | 趋势/背景 | 政策、融资、趋势币 |
| 🔴 **L1** | 噪音（已降级） | 招聘、八卦、营销稿 |

> ⚠️ 极端数值（如资金费率年化 >1000%）会被标 **疑似异常/骗局**，提醒你警惕新币/低流动性的伪机会。

### 目前支持 3 个赛道

- **加密Web3**：DeFi 收益率、资金费率、趋势（链上 API）
- **AI工具**：模型/工具/红利资讯（RSS）
- **开发者开源**：GitHub 新晋爆款项目 + 技术社区讨论（GitHub API + Reddit/HN）

---

👉 **现在就开始**：点左侧「🛰️ 信息源 & 扫描」，选一个赛道扫描，再去「📥 收件箱」。
""")
    counts = get_counts()
    m = st.columns(4)
    m[0].metric("待评估信号", counts["new"])
    m[1].metric("🟢 L4 即时可行动", counts["L4"])
    m[2].metric("🟡 L3 待评估", counts["L3"])
    m[3].metric("⚠️ 异常预警", counts["scam"])


def page_inbox():
    st.header("📥 收件箱 · 待评估信号")
    st.info(
        "**这一步做什么**：机器已采集信号并按相关度+机会等级排序。"
        "你的任务是**快速扫一眼，把值得做成机会的点「⬆️晋升」，没用的「🗑️过滤」**。",
        icon="💡"
    )

    tracks = list_tracks_in_db()
    track_map = {"全部赛道": None} | {t: t for t in tracks}
    cT = st.columns([2, 2, 2, 2, 3, 2])
    track_pick = cT[0].selectbox("🎯 赛道", list(track_map.keys()))
    level_filter = cT[1].selectbox(
        "🏷️ 机会等级",
        ["全部", "🟢 L4 即时可行动", "🟡 L3 待评估", "🔵 L2 背景", "🔴 L1 噪音"],
    )
    min_rel = cT[2].slider("最低相关度", 0.0, 1.0, 0.4, 0.1)
    limit = cT[3].selectbox("显示数量", [20, 50, 100, 200], index=0)
    keyword = cT[4].text_input("🔎 关键词", "", placeholder="如：APY / 空投 / 免费 / 资金费率")
    sources = list_sources()
    src_map = {"全部来源": None} | {s["name"]: s["id"] for s in sources}
    src_pick = cT[5].selectbox("来源", list(src_map.keys()))

    level_map = {"🟢 L4 即时可行动": 4, "🟡 L3 待评估": 3, "🔵 L2 背景": 2, "🔴 L1 噪音": 1}
    level_v = level_map.get(level_filter)

    signals = fetch_signals(
        "new", min_rel, limit, keyword.strip(),
        src_map[src_pick], track_map[track_pick], level=level_v,
    )
    st.caption(f"当前命中 {len(signals)} 条 · 收件箱待评估总数 {get_counts()['new']}")
    if not signals:
        st.warning("没有符合条件的信号。去「🛰️ 信息源 & 扫描」选赛道扫描，或放宽筛选。")
        return

    type_icon = {"yield": "💰", "funding": "📈", "trending": "🔥", "listing": "🆕", "news": "📰"}
    level_icon = {4: "🟢", 3: "🟡", 2: "🔵", 1: "🔴", 0: "⚪"}
    for s in signals:
        rel = s.get("ai_relevance") or 0
        sig_type = s.get("signal_type") or "news"
        icon = type_icon.get(sig_type, "📄")
        level = s.get("level") or 0
        lvl_icon = level_icon.get(level, "⚪")
        scam = s.get("scam_flag") or 0
        published = (s.get("published") or "")[:16]
        with st.container(border=True):
            top = st.columns([6, 1])
            scam_badge = " ⚠️ **疑似异常/骗局**" if scam else ""
            top[0].markdown(f"{lvl_icon} L{level} · {icon} **{s['raw_title']}**{scam_badge}")
            top[1].markdown(f"`{rel:.2f}`")
            if s.get("metric_value") is not None and s.get("metric_label"):
                st.markdown(f"**📊 {s['metric_label']}: `{s['metric_value']:.2f}`**")
            meta = f"赛道: {s.get('track','-')} · 来源: {s.get('source_name','?')} (L{s.get('source_layer','?')})"
            if published:
                meta += f" · 🕒 {published}"
            if s.get("ai_tags"):
                meta += f" · 🏷️ {s['ai_tags']}"
            st.caption(meta)
            if s.get("url"):
                st.caption(f"🔗 {s['url']}")
            with st.expander("详情"):
                st.write((s.get("raw_content") or "")[:1000] or "（无详情）")

            btns = st.columns([1, 1, 4])
            if btns[0].button("⬆️ 晋升为机会", key=f"promote_{s['id']}"):
                oid = promote_signal(s["id"], s["raw_title"], (s.get("raw_content") or "")[:300])
                st.success(f"已晋升为机会卡片 #{oid}，去「🎯 机会卡片」评估。")
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
        half_life = c2.selectbox(
            "时效/半衰期", scorer.HALF_LIFE_OPTIONS,
            index=scorer.HALF_LIFE_OPTIONS.index(o["half_life"])
            if o.get("half_life") in scorer.HALF_LIFE_OPTIONS else 0,
        )
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
        judgment = c3.selectbox(
            "我的判断", scorer.JUDGMENT_OPTIONS,
            index=scorer.JUDGMENT_OPTIONS.index(o["judgment"])
            if o.get("judgment") in scorer.JUDGMENT_OPTIONS else 0,
        )
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
            st.rerun()

    # 框架结论（基于已保存到数据库的分数）
    saved_scores = {f: (o.get(f) or 0) for f, *_ in scorer.DIMENSIONS}
    total = scorer.weighted_total(saved_scores)
    dec, why_dec = scorer.decision(saved_scores)
    m = st.columns(3)
    m[0].metric("加权总分(已保存)", f"{total}/{scorer.MAX_TOTAL}")
    m[1].metric("框架建议", dec)
    m[2].caption(why_dec)
    st.caption("提示：调整滑块后需点「💾 保存评估」，结论才会更新。")

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

    opps = (fetch_opportunities("published")
            + fetch_opportunities("tracking")
            + fetch_opportunities("reviewed"))
    if not opps:
        st.info("还没有已发布的机会。先在「机会卡片」里评估并发布。")
        return

    HIT_OPTIONS = ["未判定", "hit(命中)", "miss(看错)", "neutral(中性)"]
    HIT_VAL = {"hit(命中)": "hit", "miss(看错)": "miss", "neutral(中性)": "neutral"}
    HIT_REVERSE = {v: k for k, v in HIT_VAL.items()}

    for o in opps:
        with st.container(border=True):
            st.markdown(f"**#{o['id']} {o['title']}**　· 判断: {o.get('judgment','-')} · 发布于 {o.get('published_at','-')}")
            c = st.columns([3, 1])
            outcome = c[0].text_input("实际结果", o.get("outcome") or "", key=f"out_{o['id']}")
            saved_hit = HIT_REVERSE.get(o.get("outcome_hit") or "", "未判定")
            hit = c[1].selectbox(
                "命中?", HIT_OPTIONS, index=HIT_OPTIONS.index(saved_hit),
                key=f"hit_{o['id']}",
            )
            if st.button("保存", key=f"savetrack_{o['id']}"):
                hit_val = HIT_VAL.get(hit)
                update_opportunity(o["id"], {
                    "outcome": outcome, "outcome_hit": hit_val,
                    "status": "reviewed" if hit_val else "tracking",
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
    m[2].metric("🟢 L4 即时可行动", counts["L4"])
    m[3].metric("⚠️ 异常预警", counts["scam"])

    st.divider()
    st.subheader("① 选赛道扫描")
    st.caption("不同赛道用不同数据源：加密=链上数据API（收益率/资金费率/趋势），AI=资讯RSS。")
    from tracks import list_tracks as _lt
    track_objs = _lt()
    labels = {f"{t.name}（{t.key}）": t.key for t in track_objs}
    pick = st.selectbox("赛道", list(labels.keys()))
    track_key = labels[pick]
    track_obj = next(t for t in track_objs if t.key == track_key)
    st.caption(f"📖 {track_obj.desc}")

    if st.button("🔄 立即扫描该赛道", type="primary"):
        log = st.empty()
        with st.spinner("采集中…（加密赛道会实时拉取收益率/资金费率/趋势）"):
            total = 0
            # API 采集器
            for cls in track_obj.api_collectors:
                col = cls()
                try:
                    i, _ = col.run()
                    total += i
                except Exception as e:
                    st.warning(f"{col.name} 失败: {e}")
            # RSS
            if track_obj.rss_track:
                from collectors.rss_collector import collect_all
                rss = collect_all(track=track_obj.rss_track)
                total += rss["inserted"]
            # 初筛
            from pipeline.filter import run_rule_filter
            run_rule_filter(only_new=True, track=track_obj.name)
            from config import config
            if config.ai_ready():
                from pipeline.ai_tagger import run_ai_tagger
                run_ai_tagger(limit=30)
        st.success(f"✅ 扫描完成，新增 {total} 条信号。去「📥 收件箱」查看。")
        st.rerun()

    st.divider()
    st.subheader("② 当前信息源清单")
    with session() as conn:
        rows = conn.execute(
            "SELECT name, type, track, layer, value_rating, last_fetched, enabled "
            "FROM sources ORDER BY track, layer, value_rating DESC"
        ).fetchall()
    st.dataframe([dict(r) for r in rows], use_container_width=True)
    st.caption("维护建议：往①②层（一手/社区）渗透，砍掉噪音源。命令行也可：python radar.py scan crypto")

    st.divider()
    st.subheader("③ 数据源健康检查")
    st.caption("定期检查每个源是否还活着，揪出悄悄失效的源。命令行：python radar.py health")
    if st.button("🩺 检查所有数据源"):
        with st.spinner("探测中…（逐个访问每个源）"):
            from pipeline.health import run_health_check
            rpt = run_health_check(disable_dead=False)
        st.success(f"检查完成：健康 {rpt['healthy']} · 失效 {rpt['dead']}")
        bad = [r for r in (rpt["rss"] + rpt["api"]) if not r["healthy"]]
        if bad:
            st.error("以下源失效，建议更新 sources_seed*.py 里的 URL：")
            st.dataframe(
                [{"名称": r["name"], "赛道": r.get("track", ""), "说明": r["detail"]} for r in bad],
                use_container_width=True,
            )
        else:
            st.balloons()
            st.info("所有源健康 ✅")


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_briefing(opps: list[dict]) -> str:
    """把机会卡片渲染成 Markdown 简报（对应 templates/每周简报.md 结构）。"""
    from datetime import date
    # 自动汇总赛道（不再硬编码）
    tracks_in = sorted({(o.get("track") or "未分类") for o in opps})
    track_label = " / ".join(tracks_in) if tracks_in else "未分类"
    lines: list[str] = []
    lines.append(f"# 机会雷达 · 简报（{date.today().isoformat()}）")
    lines.append("")
    lines.append(f"> 本期覆盖赛道：{track_label} · 精选机会 {len(opps)} 个。")
    lines.append("")
    lines.append("## 📋 本期速览（30秒版）")
    lines.append("")
    for i, o in enumerate(opps, 1):
        j = o.get("judgment") or "—"
        lines.append(f"{i}. **{o['title']}** —— {(o.get('summary') or '').strip()[:50]}（{j}）")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 🎯 机会详情")
    lines.append("")
    for o in opps:
        total = scorer.weighted_total(o)
        lines.append(f"### 🎯 {o['title']}")
        lines.append("")
        lines.append(f"- **赛道/维度**：{o.get('track','AI工具')} / {o.get('dimension','-')}")
        if o.get("summary"):
            lines.append(f"- **是什么**：{o['summary']}")
        if o.get("why_matters"):
            lines.append(f"- **为什么值得关注**：{o['why_matters']}")
        if o.get("risks"):
            lines.append(f"- **⚠️ 风险与坑**：{o['risks']}")
        if o.get("fit_for"):
            lines.append(f"- **适合谁**：{o['fit_for']}")
        if o.get("half_life"):
            lines.append(f"- **时效**：{o['half_life']}")
        lines.append(f"- **我的判断**：{o.get('judgment','-')}　|　评分 {total}/{scorer.MAX_TOTAL}")
        if o.get("judgment_reason"):
            lines.append(f"  - 理由：{o['judgment_reason']}")
        if o.get("disclosure") and o["disclosure"] != "无":
            lines.append(f"- **利益披露**：{o['disclosure']}")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "*免责声明：本简报仅为信息分享与研究交流，不构成任何投资、财务或法律建议，"
        "不构成任何买卖推荐。信息可能有误或延迟，请自行核实、独立决策、自负风险。*"
    )
    return "\n".join(lines)


def page_briefing():
    st.header("📤 分发中心")
    st.info(
        "**这一步做什么**：把评估好的机会**送到用户面前**。"
        "用户不该来这个网页——他们应该在公众号/小红书/Telegram/RSS 里收到你的机会。", icon="📣"
    )

    drafts = fetch_opportunities("draft")
    published = (fetch_opportunities("published") + fetch_opportunities("reviewed")
                 + fetch_opportunities("tracking"))
    pool = published + drafts
    if not pool:
        st.warning("还没有机会卡片。先去「收件箱」晋升、在「机会卡片」评估并发布。")
        return

    label = {f"#{o['id']} {o['title'][:36]} [{o.get('status')}]": o for o in pool}
    published_ids = {o["id"] for o in published}
    picked = st.multiselect(
        "选择要分发的机会（默认选中已发布的）",
        list(label.keys()),
        default=[k for k, o in label.items() if o["id"] in published_ids],
    )
    chosen = [label[k] for k in picked]
    if not chosen:
        st.warning("请至少选择一个机会。")
        return

    from publishers import exporters

    tab1, tab2, tab3, tab4 = st.tabs(["📝 文案导出", "🤖 Telegram", "📡 RSS", "📧 邮件"])

    # --- 文案导出（公众号/小红书/纯文本）---
    with tab1:
        st.caption("一次评估，多渠道文案。复制到对应平台，人工润色后发布。")
        fmt = st.radio("选择渠道格式", list(exporters.FORMATS.keys()), horizontal=True)
        content = exporters.FORMATS[fmt](chosen)
        st.download_button(f"⬇️ 下载{fmt}文案", content,
                           file_name=f"机会雷达_{fmt}.md", mime="text/markdown")
        st.code(content, language="markdown")

    # --- Telegram ---
    with tab2:
        from publishers.telegram_pub import tg_ready, publish_opportunities, chat_for_track
        # 按选中机会的赛道判断
        tracks_sel = sorted({(o.get("track") or "") for o in chosen})
        st.caption(f"将按赛道路由到对应频道。选中机会涉及赛道：{', '.join(tracks_sel) or '-'}")
        for tk in tracks_sel:
            ch = chat_for_track(tk)
            status = f"→ {ch}" if ch else "⚠️ 未配置频道"
            st.write(f"- {tk}: {status}")
        if not any(chat_for_track(tk) for tk in tracks_sel):
            st.warning(
                "对应赛道未配置频道。在 `engine/.env` 设置：\n\n"
                "`RADAR_TG_ENABLED=true`、`RADAR_TG_BOT_TOKEN=...`、\n"
                "`RADAR_TG_CHAT_CRYPTO=@你的加密频道`（一个频道一个赛道）"
            )
        else:
            if st.button("🤖 按赛道推送到对应频道", type="primary"):
                with st.spinner("推送中…"):
                    r = publish_opportunities(chosen)
                if r["skipped"]:
                    st.warning("Telegram 未启用，已跳过。")
                else:
                    st.success(f"推送完成：成功 {r['sent']}，失败 {r['failed']}。")
                    if r["errors"]:
                        st.error("；".join(r["errors"][:3]))

    # --- RSS + 公开页 ---
    with tab3:
        st.caption("生成 RSS feed.xml + 公开页 index.html，用户订阅你的机会流（不依赖任何平台）。")
        from publishers.rss_out import write_feed, build_feed
        from publishers.site_out import write_site
        col_a, col_b = st.columns(2)
        if col_a.button("📡 生成 feed.xml"):
            path, n = write_feed()
            st.success(f"RSS 已生成：{path}（{n} 条）")
        if col_b.button("🌐 生成公开页 index.html"):
            path, n = write_site()
            st.success(f"公开页已生成：{path}（{n} 条）")
            st.caption("托管到 GitHub Pages / 对象存储即可对外访问。")
        with st.expander("预览 RSS 内容"):
            st.code(build_feed(limit=10), language="xml")

    # --- 邮件（占位，下一阶段）---
    with tab4:
        st.caption("邮件 Newsletter 是沉淀'可带走名单'的核心渠道，规划在下一阶段接入。")
        st.info("当前可先用「文案导出」的内容，手动粘贴到你的邮件工具群发。")

    st.divider()
    st.caption(f"已选 {len(chosen)} 个机会。提示：分发前确保已在「机会卡片」填好风险与判断。")


# ---------------- 导航 ----------------
PAGES = {
    "🏁 使用引导": page_guide,
    "📥 收件箱": page_inbox,
    "🎯 机会卡片": page_opportunities,
    "📈 战绩追踪": page_track,
    "📤 分发中心": page_briefing,
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
