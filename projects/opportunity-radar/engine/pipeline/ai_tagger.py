"""AI 初筛打标：用大模型给信号评相关度并打标签（可选，需配置 AI）。

设计：
- 用 OpenAI 兼容的 Chat Completions 接口，任何兼容服务都能用。
- 只做"初筛"——评估这条信号作为「AI 工具/红利机会」的相关度，给 0-1 分 + 标签 + 一句理由。
- 最终判断仍由人在评估工作台完成（人机分工铁律）。
- 未配置 AI 时，本模块跳过，规则初筛(filter.py)作为兜底。

成本控制：用便宜模型；只处理规则初筛后仍需判断的信号；可限量。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import config  # noqa: E402
from db import session  # noqa: E402

SYSTEM_PROMPT = """你是一个 AI 行业机会的初筛助手。给定一条资讯信号，判断它作为
"AI 工具 / AI 红利机会"对普通用户或从业者的相关度与价值。

机会的例子：新工具/新模型发布、限免或免费额度、降价、开源、值得关注的新玩法、
重要能力更新、政策红利。噪音的例子：招聘、纯融资八卦、与AI工具无关的内容、营销软文。

只输出 JSON，格式：
{"relevance": 0.0-1.0 的数字, "tags": ["标签1","标签2"], "reason": "不超过20字的中文理由"}
relevance 越高表示越值得人工进一步评估。"""


def _call_ai(title: str, content: str) -> dict | None:
    """调用 AI，返回 {relevance, tags, reason} 或 None（失败）。"""
    user_msg = f"标题：{title}\n摘要：{content[:500]}"
    payload = {
        "model": config.AI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {config.AI_API_KEY}",
        "Content-Type": "application/json",
    }
    url = config.AI_BASE_URL.rstrip("/") + "/chat/completions"
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=config.HTTP_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        parsed = json.loads(text)
        return {
            "relevance": float(parsed.get("relevance", 0)),
            "tags": parsed.get("tags", []),
            "reason": str(parsed.get("reason", ""))[:50],
        }
    except Exception as e:
        print(f"  [WARN] AI 调用失败: {e}")
        return None


def run_ai_tagger(limit: int = 30, min_rule_score: float = 0.0) -> dict:
    """对收件箱中 status='new' 的信号做 AI 打标。

    limit: 单次最多处理多少条（控成本）。
    min_rule_score: 只处理规则相关度 >= 此值的（先跑 filter.py 再跑这个更省钱）。
    """
    if not config.ai_ready():
        print("AI 未启用（RADAR_AI_ENABLED=false 或缺少 API KEY），跳过 AI 打标。")
        print("→ 规则初筛(filter.py)已可作为排序兜底。")
        return {"processed": 0, "skipped_ai": True}

    stats = {"processed": 0, "skipped_ai": False}
    with session() as conn:
        rows = conn.execute(
            """SELECT * FROM signals
               WHERE status = 'new' AND COALESCE(ai_relevance, 0) >= ?
               ORDER BY ai_relevance DESC
               LIMIT ?""",
            (min_rule_score, limit),
        ).fetchall()
        for row in rows:
            s = dict(row)
            result = _call_ai(s["raw_title"] or "", s["raw_content"] or "")
            if result is None:
                continue
            tags = ",".join(result["tags"][:8])
            conn.execute(
                "UPDATE signals SET ai_relevance = ?, ai_tags = ?, ai_reason = ? WHERE id = ?",
                (result["relevance"], tags, result["reason"], s["id"]),
            )
            stats["processed"] += 1
            print(f"  [{result['relevance']:.2f}] {s['raw_title'][:40]} — {result['reason']}")
    return stats


if __name__ == "__main__":
    st = run_ai_tagger(limit=30)
    if not st.get("skipped_ai"):
        print(f"\nAI 打标完成：处理 {st['processed']} 条。")
