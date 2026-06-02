"""多格式文案导出：把机会卡片渲染成不同渠道的文案。

一次加工、多渠道渲染。各渠道风格不同：
- 公众号：结构化、小标题、适度 emoji、含完整风险与免责。
- 小红书：短、钩子开头、口语、话题标签、分点、含风险提示。
- 纯文本/Telegram：紧凑、要点优先。

所有输出都带免责声明（合规）。
"""
from __future__ import annotations

from datetime import date

DISCLAIMER = (
    "免责声明：本内容仅为信息分享与研究交流，不构成任何投资、财务或法律建议，"
    "不构成买卖推荐。信息可能有误或延迟，请自行核实、独立决策、自负风险。"
)


def _tracks_of(opps: list[dict]) -> str:
    return " / ".join(sorted({(o.get("track") or "未分类") for o in opps}))


def export_wechat(opps: list[dict]) -> str:
    """公众号版：结构化、适合长图文。"""
    L = []
    L.append(f"# 机会雷达 | {_tracks_of(opps)} 精选（{date.today().isoformat()}）")
    L.append("")
    L.append(f"> 本期从大量信号中筛出 {len(opps)} 个值得关注的机会，含判断与风险。")
    L.append("")
    L.append("## 📋 本期速览")
    for i, o in enumerate(opps, 1):
        L.append(f"{i}. **{o['title']}** —— {(o.get('summary') or '').strip()[:50]}")
    L.append("")
    for o in opps:
        L.append(f"## 🎯 {o['title']}")
        if o.get("summary"):
            L.append(f"**是什么**：{o['summary']}")
        if o.get("why_matters"):
            L.append(f"\n**为什么值得关注**：{o['why_matters']}")
        if o.get("risks"):
            L.append(f"\n**⚠️ 风险与坑**：{o['risks']}")
        if o.get("fit_for"):
            L.append(f"\n**适合谁**：{o['fit_for']}")
        if o.get("half_life"):
            L.append(f"\n**时效**：{o['half_life']}")
        if o.get("judgment"):
            L.append(f"\n**我的判断**：{o['judgment']}"
                     + (f"（{o['judgment_reason']}）" if o.get('judgment_reason') else ""))
        if o.get("disclosure") and o["disclosure"] != "无":
            L.append(f"\n*利益披露：{o['disclosure']}*")
        L.append("")
    L.append("---")
    L.append(f"*{DISCLAIMER}*")
    return "\n".join(L)


def export_xiaohongshu(opps: list[dict]) -> str:
    """小红书版：短、钩子、话题标签。一条笔记建议聚焦 1-3 个机会。"""
    L = []
    n = len(opps)
    # 钩子标题
    L.append(f"🔥 {_tracks_of(opps)}本周{n}个机会，第{min(n,2)}个我重点看")
    L.append("")
    L.append("最近扫了一圈，挑出这几个值得关注的👇")
    L.append("")
    for i, o in enumerate(opps, 1):
        L.append(f"{i}️⃣ {o['title']}")
        if o.get("summary"):
            L.append(f"　{o['summary'][:60]}")
        if o.get("risks"):
            L.append(f"　⚠️ 注意：{o['risks'][:50]}")
        if o.get("judgment"):
            L.append(f"　👉 我的看法：{o['judgment']}")
        L.append("")
    L.append("⚠️ 都是信息分享不是投资建议，自己判断哈")
    L.append("")
    # 话题标签
    tag_pool = {"加密Web3": "#web3 #加密货币 #defi",
                "AI工具": "#AI工具 #人工智能 #效率",
                "开发者开源": "#开源 #程序员 #github"}
    tags = set()
    for o in opps:
        tags.add(tag_pool.get(o.get("track"), "#搞钱 #机会"))
    L.append(" ".join(tags) + " #信息差 #搞钱")
    return "\n".join(L)


def export_plain(opps: list[dict]) -> str:
    """纯文本/Telegram 版：紧凑。"""
    L = []
    L.append(f"【机会雷达】{_tracks_of(opps)} · {date.today().isoformat()} · {len(opps)}个机会")
    L.append("")
    for i, o in enumerate(opps, 1):
        L.append(f"{i}. {o['title']}")
        if o.get("summary"):
            L.append(f"   {o['summary'][:80]}")
        if o.get("risks"):
            L.append(f"   ⚠️ {o['risks'][:60]}")
        if o.get("judgment"):
            L.append(f"   判断: {o['judgment']}")
        L.append("")
    L.append(DISCLAIMER)
    return "\n".join(L)


def export_single_telegram(o: dict) -> str:
    """单条机会的 Telegram 消息（Markdown）。"""
    lines = [f"🎯 *{_md_escape(o['title'])}*"]
    if o.get("track"):
        lines.append(f"赛道: {o['track']}")
    if o.get("summary"):
        lines.append(f"\n{o['summary']}")
    if o.get("why_matters"):
        lines.append(f"\n💡 {o['why_matters']}")
    if o.get("risks"):
        lines.append(f"\n⚠️ 风险: {o['risks']}")
    if o.get("judgment"):
        lines.append(f"\n👉 判断: {o['judgment']}")
    lines.append(f"\n_{DISCLAIMER}_")
    return "\n".join(lines)


def _md_escape(text: str) -> str:
    """Telegram Markdown 转义。"""
    for ch in ["_", "*", "`", "["]:
        text = text.replace(ch, "\\" + ch)
    return text


FORMATS = {
    "公众号": export_wechat,
    "小红书": export_xiaohongshu,
    "纯文本/Telegram": export_plain,
}
