"""评估辅助：把知识库的六维评估框架固化为常量与计算逻辑。

对应 knowledge-base/03-机会评估方法论/01-机会评估检查清单.md：
六维 + 权重，加权总分 /75，并给出决策建议。
这是"人工评估"的辅助——把框架结构化，方便在工作台里打分。
"""
from __future__ import annotations

# 维度: (字段名, 中文名, 权重, 说明)
DIMENSIONS = [
    ("score_spread", "净价差", 3, "价差减去摩擦后还剩多少"),
    ("score_capital", "资金效率", 2, "周转快慢、年化高低"),
    ("score_scale", "可规模化", 2, "放量后价差是否衰减"),
    ("score_moat", "护城河", 3, "价差归你独有的程度"),
    ("score_risk", "风险可控", 3, "最坏损失是否可控可度量"),
    ("score_compliance", "合规匹配", 2, "合法性 + 与自身能力匹配"),
]

MAX_TOTAL = sum(w for _, _, w, _ in DIMENSIONS) * 5  # 75

# 一票否决项（得 1 分则直接放弃）
VETO_FIELDS = {"score_risk", "score_compliance"}


def weighted_total(scores: dict) -> int:
    """计算加权总分（满分 75）。"""
    total = 0
    for field, _, weight, _ in DIMENSIONS:
        total += int(scores.get(field, 0)) * weight
    return total


def has_veto(scores: dict) -> bool:
    """是否触发一票否决（风险或合规 = 1）。"""
    return any(int(scores.get(f, 0)) == 1 for f in VETO_FIELDS)


def decision(scores: dict) -> tuple[str, str]:
    """根据总分和否决项给出决策建议，返回 (结论, 说明)。"""
    if has_veto(scores):
        return "放弃", "风险或合规项得 1 分，触发一票否决，不看总分"
    total = weighted_total(scores)
    if total >= 55:
        return "深入研究", f"加权 {total}/75 ≥ 55，值得深入 + 小成本验证"
    if total >= 40:
        return "观察", f"加权 {total}/75 在 40-54，列入追踪等条件成熟"
    return "放弃", f"加权 {total}/75 < 40，性价比不足"


# 套利维度选项（供工作台下拉）
ARBITRAGE_DIMENSIONS = [
    "空间套利", "时间套利", "信息套利", "形态加工套利",
    "信用风险套利", "资质监管套利", "规模套利", "统计概率套利",
]

HALF_LIFE_OPTIONS = ["快(需立即行动)", "中(可观望几天)", "长(长期有效)"]
JUDGMENT_OPTIONS = ["关注", "观望", "跳过"]


if __name__ == "__main__":
    # 自测
    demo = {
        "score_spread": 4, "score_capital": 5, "score_scale": 3,
        "score_moat": 3, "score_risk": 4, "score_compliance": 5,
    }
    print("维度框架：")
    for f, name, w, desc in DIMENSIONS:
        print(f"  {name}(x{w}): {desc}")
    print(f"\n示例打分加权总分: {weighted_total(demo)}/{MAX_TOTAL}")
    print(f"决策建议: {decision(demo)}")
