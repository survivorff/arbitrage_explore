"""规则初筛：在调用 AI 之前，用关键词规则做一轮便宜的粗筛。

目的：
- 把明显是"机会信号"的关键词（限免/降价/发布/开源…）顶上来。
- 把明显噪音/无关的标记下去，减少后续 AI 调用量（省钱）。

这是"便宜的初筛"，最终判断仍由人在评估工作台完成。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import session  # noqa: E402

# 机会信号关键词（命中=更可能是值得关注的机会，加分）
OPPORTUNITY_KEYWORDS = [
    # 中文
    "免费", "限免", "开源", "降价", "发布", "上线", "推出", "测试版", "公测",
    "内测", "额度", "福利", "红利", "教程", "实测", "对比", "新模型", "新功能",
    "alpha", "beta",
    # 加密 Web3
    "空投", "airdrop", "上线", "上币", "listing", "质押", "staking", "收益",
    "apy", "apr", "资金费率", "funding", "套利", "arbitrage", "主网", "mainnet",
    "快照", "snapshot", "测试网", "testnet", "积分", "points",
    # 英文
    "free", "open source", "open-source", "launch", "release", "released",
    "now available", "introducing", "announces", "announced", "price",
    "pricing", "discount", "credits", "waitlist", "preview", "API",
]

# 噪音/低相关关键词（命中=减分，倾向过滤）
NOISE_KEYWORDS = [
    "招聘", "hiring", "webinar", "广告", "sponsored", "赞助",
    "live now", "我们正在招聘",
]

# 数据类信号（来自 API 的量化机会）天然就是高相关，无需关键词判断
DATA_SIGNAL_TYPES = {"yield", "funding", "trending", "listing"}

# 骗局/异常预警关键词（命中=置 scam_flag，并降级为噪音）
SCAM_KEYWORDS = [
    "保证收益", "稳赚", "包赚", "无风险高息", "拉人头", "下线",
    "guaranteed returns", "no risk high yield", "ponzi",
]


def detect_scam(title: str, content: str) -> bool:
    text = f"{title} {content}".lower()
    return any(kw.lower() in text for kw in SCAM_KEYWORDS)


def score_by_rules(title: str, content: str) -> tuple[float, list[str]]:
    """返回 (规则相关度 0-1, 命中的机会关键词列表)。"""
    text = f"{title} {content}".lower()
    # 去重防止同一关键词在两个分类里重复加分
    seen: set[str] = set()
    hits: list[str] = []
    for kw in OPPORTUNITY_KEYWORDS:
        kl = kw.lower()
        if kl in seen:
            continue
        if kl in text:
            hits.append(kw)
            seen.add(kl)
    noise = []
    seen.clear()
    for kw in NOISE_KEYWORDS:
        kl = kw.lower()
        if kl in seen:
            continue
        if kl in text:
            noise.append(kw)
            seen.add(kl)

    # 简单打分：机会词每个 +0.2（封顶 1.0），噪音词每个 -0.3
    score = min(1.0, 0.2 * len(hits)) - 0.3 * len(noise)
    score = max(0.0, min(1.0, score))
    return score, hits


def _classify_data_signal(sig: dict) -> tuple[int, int, float]:
    """对 API 数据类信号分级：返回 (level, scam_flag, score)。

    L4 即时可行动：APY 在合理区间(10-50%) + TVL 足够大；资金费率 30-200% 年化。
    L3 待评估：APY 50-200% 或资金费率 200-500%（需要研究是否可持续/有坑）。
    L2/scam：APY > 500% 或资金费率 > 1000% —— 极端值，标 scam_flag 让用户警惕。
    """
    sig_type = sig.get("signal_type")
    val = sig.get("metric_value")

    # listing 类（币安公告/新协议）可能没有 metric_value，先处理
    if sig_type == "listing":
        label = sig.get("metric_label") or ""
        title = (sig.get("raw_title") or "")
        if label == "币安公告":
            if "上币" in title or "空投" in title:
                return 4, 0, 0.95    # 上币/空投=最强信息差
            if "下架" in title:
                return 3, 0, 0.7
            if "合约上新" in title:
                return 4, 0, 0.85
            return 3, 0, 0.7
        return 3, 0, 0.7             # 新协议（DefiLlama）

    if val is None:
        return 3, 0, 0.6

    if sig_type == "yield":
        apy = abs(val)
        if apy >= 500:
            return 1, 1, 0.5    # 极高 APY 通常是貔貅/投机币，标骗局
        if apy >= 100:
            return 3, 0, 0.7    # 高息但需评估
        if apy >= 10:
            return 4, 0, 0.9    # 合理高息，即时可行动
        return 2, 0, 0.5

    if sig_type == "funding":
        annual = abs(val)
        if annual >= 1000:
            return 1, 1, 0.4    # 极端值（新币 + 低流动性，做不了）
        if annual >= 200:
            return 3, 0, 0.7    # 高费率，需要看是否能持续吃
        if annual >= 30:
            return 4, 0, 0.9    # 套利窗口
        return 2, 0, 0.5

    if sig_type == "trending":
        label = sig.get("metric_label") or ""
        if label == "Stars":
            # GitHub 新晋项目：用 star 数分级
            stars = abs(val)
            if stars >= 1000:
                return 4, 0, 0.9
            if stars >= 300:
                return 3, 0, 0.75
            return 2, 0, 0.6
        if label == "Likes":
            # HuggingFace 热门模型/应用：用 likes 分级
            likes = abs(val)
            if likes >= 300:
                return 4, 0, 0.9    # 现象级热门
            if likes >= 80:
                return 3, 0, 0.75
            return 2, 0, 0.6
        if "涨幅" in label:
            # 板块/链上涨幅：涨幅越大越热
            chg = abs(val)
            if "链上" in label:
                # 链上单池热点：极强信号但高风险
                if chg >= 50:
                    return 4, 0, 0.92   # 爆拉，最热一手
                if chg >= 15:
                    return 3, 0, 0.8
                return 2, 0, 0.65
            # 板块叙事
            if chg >= 20:
                return 3, 0, 0.8
            return 2, 0, 0.65
        return 2, 0, 0.6            # 其他趋势（加密趋势币等）

    return 3, 0, 0.7


def run_rule_filter(only_new: bool = True, track: str | None = None) -> dict:
    """对收件箱里的信号跑规则初筛，赋值 ai_relevance + level + scam_flag。"""
    stats = {"processed": 0, "L4": 0, "L3": 0, "L2": 0, "L1": 0, "scam": 0}
    with session() as conn:
        conds = ["status = 'new'"] if only_new else []
        params: list = []
        if track:
            conds.append("track = ?")
            params.append(track)
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        rows = conn.execute(f"SELECT * FROM signals {where}", params).fetchall()
        for row in rows:
            s = dict(row)
            sig_type = s.get("signal_type") or "news"

            # 1. 骗局检测（不论资讯/数据）
            scam = 1 if detect_scam(s["raw_title"] or "", s["raw_content"] or "") else 0

            # 2. 分级与打分
            if sig_type in DATA_SIGNAL_TYPES:
                level, data_scam, score = _classify_data_signal(s)
                scam = scam or data_scam
                tags = sig_type
            else:
                score, hits = score_by_rules(s["raw_title"] or "", s["raw_content"] or "")
                tags = ",".join(hits[:8])
                # 资讯型分级：根据命中关键词数量
                if scam:
                    level = 1
                elif score >= 0.6:
                    level = 3        # 多个机会词命中 → 待评估
                elif score >= 0.3:
                    level = 2        # 少量命中 → 背景
                else:
                    level = 1        # 几乎无命中 → 噪音

            if scam:
                level = 1
                score = min(score, 0.3)
                stats["scam"] += 1

            conn.execute(
                "UPDATE signals SET ai_relevance=?, ai_tags=?, level=?, scam_flag=? WHERE id=?",
                (score, tags, level, scam, s["id"]),
            )
            stats["processed"] += 1
            stats[f"L{level}"] += 1
    return stats


if __name__ == "__main__":
    st = run_rule_filter(only_new=True)
    print(
        f"规则初筛完成：处理 {st['processed']} 条 | "
        f"L4 {st.get('L4',0)} · L3 {st.get('L3',0)} · "
        f"L2 {st.get('L2',0)} · L1 {st.get('L1',0)} · ⚠️骗局 {st.get('scam',0)}"
    )
