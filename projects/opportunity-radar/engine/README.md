# 机会雷达引擎（Opportunity Radar Engine）

> MVP 版本：AI 赛道机会的 **采集 → 初筛 → 评估 → 战绩追踪** 工作台。
> 对应立项文档 `../build/05-技术开发.md`。这是项目的"对内工具系统/生产线"。

---

## 它解决什么

把"每周刷几十小时信息找 AI 机会"的活，压缩成：机器自动采集+初筛，你只对高相关信号做判断，沉淀成结构化「机会卡片」，并诚实追踪战绩。

```
信息源(RSS) → 采集 → 规则/AI初筛 → [收件箱] → 人工评估(六维框架) → [机会卡片库] → 战绩追踪
   机器                机器                       你来判断                          你来回填
```

人机分工铁律：**机器提效（采集/初筛/起草），判断和终审永远由人做**——因为你卖的就是判断和信任。

---

## 快速开始

```bash
# 1. 创建虚拟环境并安装依赖（在仓库根目录已有 .venv 可复用）
python3 -m venv .venv
.venv/bin/pip install feedparser httpx streamlit

# 2. （可选）配置 AI 辅助：复制 .env.example 为 .env 并填 key
cp .env.example .env      # 编辑 .env，设 RADAR_AI_ENABLED=true 和 API KEY

# 3. 走通加密赛道全流程（推荐先体验这个）
python radar.py init
python radar.py setup crypto     # 准备加密赛道数据源
python radar.py scan crypto      # 采集真实收益率/资金费率/趋势+资讯
python radar.py ui               # 启动评估工作台

# AI 赛道则用： setup ai / scan ai
```

> 详细图文走查见 `WALKTHROUGH-加密赛道.md`。

---

## 命令行（radar.py）

| 命令 | 作用 |
|------|------|
| `init` | 初始化数据库 |
| `tracks` | 列出所有赛道 |
| `setup <track>` | 初始化某赛道数据源（crypto / ai） |
| `scan <track>` | **采集+初筛某赛道（日常用这个）** |
| `stats` | 数据概览（按赛道） |
| `ui` | 启动评估工作台 |

---

## 核心设计：按赛道可插拔的数据源

> 回应"不同赛道数据源不同"——这是架构的核心。

| 赛道 | 机会形态 | 数据源类型 | 采集器 |
|------|---------|-----------|--------|
| **加密Web3** | APY/资金费率/趋势（带数字的量化机会） | **数据 API** | DeFiLlama、Binance、CoinGecko + 加密资讯RSS |
| **AI工具** | 新工具/限免/降价（文章发布） | 资讯 RSS | 厂商博客、社区、媒体 |

新增赛道：在 `tracks.py` 注册一个 `Track`，声明它的采集器即可。

---

## 工作台（Streamlit）四个页面

1. **📥 收件箱**：按相关度排序的待评估信号，「晋升」为机会 / 「过滤」掉。
2. **🎯 机会卡片**：用知识库六维框架评估打分（风险/合规一票否决），编辑、发布。
3. **📈 战绩追踪**：给已发布机会回填实际结果（命中/看错），积累信任资产。
4. **🛰️ 信息源 & 扫描**：管理源、一键扫描、查看概览。

---

## 目录结构

```
engine/
├── radar.py            # 统一 CLI 入口（按赛道）
├── tracks.py           # 赛道定义（每个赛道声明自己的采集器）
├── config.py           # 配置（从 .env 读，密钥不入库）
├── db.py               # SQLite + 三张核心表
├── sources_seed.py        # AI 赛道 RSS 种子源
├── sources_seed_crypto.py # 加密赛道 RSS 种子源
├── collectors/         # 采集层
│   ├── base.py             # 采集器基类 + 信号写入
│   ├── rss_collector.py    # RSS 采集（按赛道过滤）
│   └── crypto_collectors.py# 加密 API 采集（收益率/资金费率/趋势）
├── pipeline/           # 处理层
│   ├── filter.py       # 规则初筛（赛道感知 + 数据信号高相关）
│   ├── ai_tagger.py    # AI 初筛打标（可选）
│   └── scorer.py       # 六维评估框架
├── ui/
│   └── app.py          # Streamlit 工作台（引导/收件箱/机会/战绩/简报/扫描）
└── WALKTHROUGH-加密赛道.md  # 图文走查
```

数据表：`sources`（信息源）→ `signals`（原始信号/收件箱，含 signal_type 和 metric 数字）→ `opportunities`（机会卡片/核心资产）。

---

## 设计原则与边界

- **最小依赖**：核心用标准库 `sqlite3`，采集 `feedparser`，AI 走 OpenAI 兼容接口。AI 未配置时规则初筛兜底。
- **数据是资产**：`opportunities` 库越积越值钱（含战绩 `outcome`），是护城河之一。
- **合规**：采集尊重源条款、控频率、标来源；密钥走 `.env`（已 gitignore）；战绩命中率仅供自我校准，**不可用于"保证收益"宣传**（见 `../06-合规与信任框架.md`）。
- **MVP 不含**：自动生成文案、自动分发、数据看板（阶段2-3，见 `../build/05-技术开发.md`）。

---

## 下一步（阶段2-3）

- 加工器：机会卡片 → AI 起草各渠道文案（人工终审）。
- 更多采集源：API / 网页 / 社区。
- 分发器、数据看板、FastAPI+前端正式化、SQLite→PostgreSQL。
