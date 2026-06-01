"""数据库层：SQLite + 标准库 sqlite3，零 ORM 依赖。

三张核心表（对应 build/05-技术开发.md 的设计）：
- sources       信息源（生产资料）
- signals       原始信号（收件箱）
- opportunities 机会卡片（核心资产）
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from config import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    type         TEXT NOT NULL DEFAULT 'rss',   -- rss/api/web/manual
    url          TEXT,
    track        TEXT,
    layer        INTEGER DEFAULT 3,             -- 信息源层级 1-5（①一手…⑤大众）
    value_rating INTEGER DEFAULT 2,             -- 价值评级 1-3
    enabled      INTEGER NOT NULL DEFAULT 1,
    last_fetched TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS signals (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id    INTEGER REFERENCES sources(id),
    raw_title    TEXT,
    raw_content  TEXT,
    url          TEXT,
    hash         TEXT UNIQUE,                   -- 去重
    published    TEXT,                          -- 源给的发布时间
    ai_tags      TEXT,                          -- AI 初筛标签(JSON)
    ai_relevance REAL,                          -- AI 相关度 0-1
    ai_reason    TEXT,                          -- AI 给的简短理由
    status       TEXT NOT NULL DEFAULT 'new',   -- new/filtered_out/promoted
    fetched_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS opportunities (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id        INTEGER REFERENCES signals(id),
    title            TEXT NOT NULL,
    track            TEXT,
    dimension        TEXT,                       -- 套利维度
    summary          TEXT,
    why_matters      TEXT,
    risks            TEXT,                       -- JSON 数组或多行文本
    fit_for          TEXT,
    half_life        TEXT,                       -- 快/可观望/长期
    score_spread     INTEGER DEFAULT 0,
    score_capital    INTEGER DEFAULT 0,
    score_scale      INTEGER DEFAULT 0,
    score_moat       INTEGER DEFAULT 0,
    score_risk       INTEGER DEFAULT 0,
    score_compliance INTEGER DEFAULT 0,
    judgment         TEXT,                       -- 关注/观望/跳过
    judgment_reason  TEXT,
    disclosure       TEXT DEFAULT '无',
    status           TEXT NOT NULL DEFAULT 'draft',  -- draft/published/tracking/reviewed
    outcome          TEXT,                       -- 战绩：事后实际结果
    outcome_hit      TEXT,                       -- hit/miss/neutral
    channels         TEXT,                       -- 已发布渠道(JSON)
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    published_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);
CREATE INDEX IF NOT EXISTS idx_signals_relevance ON signals(ai_relevance);
CREATE INDEX IF NOT EXISTS idx_opp_status ON opportunities(status);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def session() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """创建表（幂等）。"""
    with session() as conn:
        conn.executescript(SCHEMA)


if __name__ == "__main__":
    init_db()
    print(f"数据库已初始化: {config.DB_PATH}")
