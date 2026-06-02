"""加密「一手热点机会」采集器 —— 真正能用信息差做投资/做项目的实时 alpha。

区别于 crypto_collectors（量化套利：收益率/资金费率），这里抓的是：
- 🆕 交易所上币公告（币安）—— 最强信息差，上币常瞬间拉盘
- 🪂 空投/活动（币安 HODLer 等）—— 直接的红利机会
- 🔥 链上趋势池（GeckoTerminal）—— 此刻正在爆拉的币/新叙事
- ⚡ 链上新池（GeckoTerminal）—— 刚上线几分钟的新币（早期/高风险）

全部免费、无需 key。⚠️ 越早期越高风险（貔貅/拉高出货），采集器会据此分级并加风险提示。
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.base import Collector, insert_signal  # noqa: E402
from config import config  # noqa: E402

TRACK = "加密Web3"


def _client(headers: dict | None = None) -> httpx.Client:
    h = {"User-Agent": config.USER_AGENT, "Accept": "application/json"}
    if headers:
        h.update(headers)
    return httpx.Client(timeout=config.HTTP_TIMEOUT, headers=h)


class BinanceAnnouncements(Collector):
    """币安公告：上币 / 永续合约 / 空投活动 —— 加密最强一手信息差。

    catalogId=48 是币安"最新公告"目录，含上新、空投、活动。
    """
    name = "币安公告"
    type = "api"
    track = TRACK
    layer = 1
    rating = 3
    PAGES = 20

    def collect(self, conn) -> tuple[int, int]:
        url = ("https://www.binance.com/bapi/composite/v1/public/cms/article/"
               f"catalog/list/query?catalogId=48&pageNo=1&pageSize={self.PAGES}")
        with _client({"User-Agent": "Mozilla/5.0"}) as c:
            data = c.get(url).json()
        articles = (data.get("data") or {}).get("articles") or []
        ins = skip = 0
        for a in articles:
            title_en = a.get("title", "")
            code = a.get("code", "")
            # 识别类型，提炼机会角度
            low = title_en.lower()
            if "will list" in low or "listing" in low or "will add" in low:
                kind, angle = "🆕上币", "交易所上币常引发拉盘，关注上线时间与抢筹/解锁节奏"
            elif "airdrop" in low or "hodler" in low:
                kind, angle = "🪂空投", "持仓/参与可得空投，属于直接红利机会"
            elif "perpetual" in low or "futures" in low:
                kind, angle = "📈合约上新", "新永续合约上线，留意开盘波动与资金费率"
            elif "delist" in low:
                kind, angle = "⚠️下架", "下架通常利空，注意持仓风险"
            else:
                kind, angle = "📢公告", "币安官方动态，可能影响相关币种"
            title = f"[{kind}] {title_en}"
            content = (
                f"币安公告：{title_en}\n类型：{kind}\n"
                f"机会角度：{angle}\n"
                f"⚠️ 注意：上币/活动信息传播极快，价差收敛快，需快速判断；谨防FOMO追高。"
            )
            url_a = f"https://www.binance.com/en/support/announcement/{code}"
            ok = insert_signal(
                conn, source_id=self._source_id, track=TRACK, signal_type="listing",
                title=title, content=content, url=url_a,
                metric_label="币安公告", dedup_key=f"binance-ann:{code}",
            )
            ins += ok
            skip += not ok
        return ins, skip


class GeckoTrendingPools(Collector):
    """GeckoTerminal 全网趋势池：此刻链上正在爆拉/吸金的币（实时热点）。"""
    name = "链上趋势(GeckoTerminal)"
    type = "api"
    track = TRACK
    layer = 1
    rating = 3
    TOP_N = 20

    def collect(self, conn) -> tuple[int, int]:
        url = "https://api.geckoterminal.com/api/v2/networks/trending_pools?page=1"
        with _client() as c:
            data = c.get(url).json()
        ins = skip = 0
        for p in data.get("data", [])[: self.TOP_N]:
            attr = p.get("attributes", {})
            name = attr.get("name", "?")
            chg = attr.get("price_change_percentage", {}) or {}
            h24 = chg.get("h24") or "0"
            vol24 = attr.get("volume_usd", {}) or {}
            vol = vol24.get("h24") or "0"
            try:
                chg_f = float(h24)
            except (ValueError, TypeError):
                chg_f = 0.0
            net = (p.get("id") or "").split("_")[0]
            title = f"[🔥链上热点] {name} · 24h {chg_f:+.0f}% · {net}"
            content = (
                f"交易对：{name}\n链：{net}\n24h涨幅：{chg_f:+.1f}%\n24h成交额：${float(vol or 0)/1e6:.1f}M\n"
                f"信号：GeckoTerminal 全网趋势榜，资金正在涌入。\n"
                f"机会角度：链上热点反映新叙事/资金动向，可顺势或挖掘相关生态。\n"
                f"⚠️ 风险：链上热点波动极大，谨防貔貅/拉高出货，务必查合约与流动性。"
            )
            url_p = f"https://www.geckoterminal.com/{net}/pools/{(p.get('id') or '').split('_',1)[-1]}"
            ok = insert_signal(
                conn, source_id=self._source_id, track=TRACK, signal_type="trending",
                title=title, content=content, url=url_p,
                metric_value=chg_f, metric_label="链上24h涨幅 %",
                dedup_key=f"geckotrend:{p.get('id')}:{datetime.now(timezone.utc).date()}",
            )
            ins += ok
            skip += not ok
        return ins, skip


CRYPTO_ALPHA_COLLECTORS = [BinanceAnnouncements, GeckoTrendingPools]


if __name__ == "__main__":
    from db import init_db
    init_db()
    for cls in CRYPTO_ALPHA_COLLECTORS:
        col = cls()
        try:
            i, s = col.run()
            print(f"[{col.name}] 新增 {i}，跳过 {s}")
        except Exception as e:
            print(f"[{col.name}] 失败: {e}")
