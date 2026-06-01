"""加密 Web3 赛道采集器：从一手数据 API 抓"机会信号"。

这些是加密赛道真正的信息差所在——不是新闻 RSS，而是带数字的量化机会：
- DeFi 收益率池（DeFiLlama）   → 高息机会、收益套利
- 永续合约资金费率（Binance）  → 资金费率套利（delta-neutral）
- 趋势/新币（CoinGecko）       → 关注度异动
- 交易所公告（RSS 兜底）       → 新币上线红利

全部使用免费、无需 API key 的公开接口。礼貌抓取、控频率。
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import config  # noqa: E402
from collectors.base import Collector, insert_signal  # noqa: E402

TRACK = "加密Web3"


def _client() -> httpx.Client:
    return httpx.Client(
        timeout=config.HTTP_TIMEOUT,
        headers={"User-Agent": config.USER_AGENT, "Accept": "application/json"},
    )


class DefiLlamaYields(Collector):
    """DeFiLlama 收益率池：筛出"高 APY + 足够 TVL"的收益机会。

    这是收益套利/搬砖的核心信号源。把异常高息的池子作为机会信号。
    """
    name = "DeFiLlama 收益率"
    type = "api"
    track = TRACK
    layer = 1          # 链上数据，一手
    rating = 3

    MIN_APY = 10.0          # 只关注 APY > 10% 的
    MIN_TVL = 2_000_000     # TVL > $2M（过滤貔貅/极小池）
    MAX_APY = 1000.0        # APY 过高通常是异常/高风险，标注但限制噪音
    TOP_N = 40

    def collect(self, conn) -> tuple[int, int]:
        with _client() as c:
            data = c.get("https://yields.llama.fi/pools").json()["data"]
        pools = [
            p for p in data
            if (p.get("apy") or 0) >= self.MIN_APY
            and (p.get("tvlUsd") or 0) >= self.MIN_TVL
            and (p.get("apy") or 0) <= self.MAX_APY
        ]
        pools.sort(key=lambda x: -(x.get("apy") or 0))
        ins = skip = 0
        for p in pools[: self.TOP_N]:
            apy = p["apy"]
            tvl_m = p["tvlUsd"] / 1e6
            stable = "稳定币" if p.get("stablecoin") else "非稳定币"
            il = "无IL风险" if p.get("ilRisk") == "no" else "有IL风险"
            title = f"[收益] {p['project']} · {p['symbol']} {apy:.1f}% APY ({p['chain']})"
            content = (
                f"协议: {p['project']} | 链: {p['chain']} | 代币: {p['symbol']}\n"
                f"APY: {apy:.2f}% | TVL: ${tvl_m:.1f}M | {stable} | {il}\n"
                f"近7日APY变化: {p.get('apyPct7D')}"
            )
            url = f"https://defillama.com/yields/pool/{p.get('pool','')}"
            ok = insert_signal(
                conn, source_id=self._source_id, track=TRACK, signal_type="yield",
                title=title, content=content, url=url,
                metric_value=apy, metric_label="APY %",
                dedup_key=f"yield:{p.get('pool')}",
            )
            ins += ok
            skip += not ok
        return ins, skip


class BinanceFunding(Collector):
    """Binance 永续合约资金费率：筛出资金费率异常的，作为资金费率套利信号。

    资金费率年化高（正或负绝对值大）→ delta-neutral 套利机会。
    """
    name = "Binance 资金费率"
    type = "api"
    track = TRACK
    layer = 1
    rating = 3

    MIN_ABS_ANNUAL = 15.0   # 年化绝对值 > 15% 才算机会
    TOP_N = 25

    def collect(self, conn) -> tuple[int, int]:
        with _client() as c:
            data = c.get("https://fapi.binance.com/fapi/v1/premiumIndex").json()
        rows = []
        for d in data:
            try:
                rate = float(d["lastFundingRate"])  # 每 8 小时
            except (KeyError, ValueError, TypeError):
                continue
            annual = rate * 3 * 365 * 100  # 年化 %
            if abs(annual) >= self.MIN_ABS_ANNUAL:
                rows.append((d["symbol"], rate, annual))
        rows.sort(key=lambda x: -abs(x[2]))
        ins = skip = 0
        for symbol, rate, annual in rows[: self.TOP_N]:
            direction = "多头付费(可做空收费)" if rate > 0 else "空头付费(可做多收费)"
            title = f"[资金费率] {symbol} 年化 {annual:+.1f}% ({direction})"
            content = (
                f"合约: {symbol} | 当期费率: {rate*100:.4f}%/8h | 年化: {annual:+.1f}%\n"
                f"方向: {direction}\n"
                f"套利思路: 现货/合约对冲吃费率(delta-neutral)，注意爆仓与费率反转风险。"
            )
            url = f"https://www.binance.com/zh-CN/futures/{symbol}"
            # 资金费率每天变，用日期+symbol 去重（同一天同合约只记一次）
            from datetime import date
            ok = insert_signal(
                conn, source_id=self._source_id, track=TRACK, signal_type="funding",
                title=title, content=content, url=url,
                metric_value=annual, metric_label="资金费率年化 %",
                dedup_key=f"funding:{symbol}:{date.today().isoformat()}",
            )
            ins += ok
            skip += not ok
        return ins, skip


class CoinGeckoTrending(Collector):
    """CoinGecko 趋势币：搜索热度榜，反映关注度异动（信息/情绪信号）。"""
    name = "CoinGecko 趋势"
    type = "api"
    track = TRACK
    layer = 2
    rating = 2

    def collect(self, conn) -> tuple[int, int]:
        with _client() as c:
            data = c.get("https://api.coingecko.com/api/v3/search/trending").json()
        ins = skip = 0
        from datetime import date
        today = date.today().isoformat()
        for entry in data.get("coins", []):
            item = entry.get("item", {})
            name = item.get("name", "?")
            sym = item.get("symbol", "")
            rank = item.get("market_cap_rank")
            title = f"[趋势] {name} ({sym}) 进入热搜榜"
            content = (
                f"代币: {name} ({sym}) | 市值排名: {rank}\n"
                f"信号: 搜索热度上升，关注度异动。注意：热度≠机会，警惕追高接盘。"
            )
            url = f"https://www.coingecko.com/en/coins/{item.get('id','')}"
            ok = insert_signal(
                conn, source_id=self._source_id, track=TRACK, signal_type="trending",
                title=title, content=content, url=url,
                metric_value=float(rank) if rank else None, metric_label="市值排名",
                dedup_key=f"trending:{item.get('id')}:{today}",
            )
            ins += ok
            skip += not ok
        return ins, skip


CRYPTO_COLLECTORS = [DefiLlamaYields, BinanceFunding, CoinGeckoTrending]


if __name__ == "__main__":
    from db import init_db
    init_db()
    for cls in CRYPTO_COLLECTORS:
        col = cls()
        try:
            i, s = col.run()
            print(f"[{col.name}] 新增 {i}，跳过 {s}")
        except Exception as e:
            print(f"[{col.name}] 失败: {e}")
