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


def score_by_rules(title: str, content: str) -> tuple[float, list[str]]:
    """返回 (规则相关度 0-1, 命中的机会关键词列表)。"""
    text = f"{title} {content}".lower()
    hits = [kw for kw in OPPORTUNITY_KEYWORDS if kw.lower() in text]
    noise = [kw for kw in NOISE_KEYWORDS if kw.lower() in text]

    # 简单打分：机会词每个 +0.2（封顶 1.0），噪音词每个 -0.3
    score = min(1.0, 0.2 * len(hits)) - 0.3 * len(noise)
    score = max(0.0, min(1.0, score))
    return score, hits


def run_rule_filter(only_new: bool = True) -> dict:
    """对收件箱里的信号跑规则初筛，把规则相关度写入 ai_relevance（AI 未启用时作为兜底排序依据）。

    注意：这里不直接 filtered_out，把判断权留给人；只是给一个初步相关度。
    """
    stats = {"processed": 0, "high": 0, "low": 0}
    with session() as conn:
        where = "WHERE status = 'new'" if only_new else ""
        rows = conn.execute(f"SELECT * FROM signals {where}").fetchall()
        for row in rows:
            s = dict(row)
            score, hits = score_by_rules(s["raw_title"] or "", s["raw_content"] or "")
            tags = ",".join(hits[:8])
            conn.execute(
                "UPDATE signals SET ai_relevance = ?, ai_tags = ? WHERE id = ?",
                (score, tags, s["id"]),
            )
            stats["processed"] += 1
            if score >= 0.4:
                stats["high"] += 1
            else:
                stats["low"] += 1
    return stats


if __name__ == "__main__":
    st = run_rule_filter(only_new=True)
    print(
        f"规则初筛完成：处理 {st['processed']} 条，"
        f"高相关 {st['high']}，低相关 {st['low']}。"
    )
