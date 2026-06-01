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

# 3. 初始化 + 导入种子源 + 首次扫描
python radar.py init
python radar.py seed
python radar.py scan      # = collect + filter + ai

# 4. 启动评估工作台
python radar.py ui        # 浏览器打开 Streamlit 界面
```

> 说明：示例中 `python` 指虚拟环境内的解释器。若用根目录 venv，直接 `/path/to/.venv/bin/python radar.py ...`。

---

## 命令行（radar.py）

| 命令 | 作用 |
|------|------|
| `init` | 初始化数据库 |
| `seed` | 导入种子信息源（AI 赛道 RSS） |
| `collect` | 采集所有 RSS 源到收件箱 |
| `filter` | 规则初筛（关键词给相关度打分） |
| `ai` | AI 初筛打标（需配置 AI，否则跳过） |
| `scan` | 一键 collect+filter+ai（**日常用这个**） |
| `stats` | 数据概览 |
| `ui` | 启动评估工作台 |

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
├── radar.py            # 统一 CLI 入口
├── config.py           # 配置（从 .env 读，密钥不入库）
├── db.py               # SQLite + 三张核心表
├── sources_seed.py     # 种子信息源
├── collectors/         # 采集层
│   └── rss_collector.py
├── pipeline/           # 处理层
│   ├── filter.py       # 规则初筛
│   ├── ai_tagger.py    # AI 初筛打标（可选）
│   └── scorer.py       # 六维评估框架
└── ui/
    └── app.py          # Streamlit 工作台
```

数据表：`sources`（信息源）→ `signals`（原始信号/收件箱）→ `opportunities`（机会卡片/核心资产）。

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
