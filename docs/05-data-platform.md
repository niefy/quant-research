# 05 · 数据平台

> 目标：为因子计算与验证提供**可复现、Point-in-Time、可追溯**的数据底座。  
> 上游：[验证流水线](04-validation-pipeline.md)　下游：[后端 API](06-backend-api.md)

---

## 1. 数据平台要解决的问题

1. **PIT（Point-in-Time）**：任何时点的因子只能使用当时可获得的数据。
2. **幸存者偏差**：历史 universe 必须是当时的成分，而不是今天的成分。
3. **可复现**：每次计算绑定不可变数据快照。
4. **多市场**：加密、A 股、美股共用一套接口，字段与日历差异由适配器吸收。
5. **来源合规**：论文/策略库的抓取、存储、分发遵守许可与 ToS。
6. **性能**：列式存储 + 分区裁剪 + 缓存，避免重复扫描。

---

## 2. 数据来源矩阵

| 来源 | 类型 | 访问方式 | 平台用途 | 合规要点 |
|---|---|---|---|---|
| Binance Public Data | 行情/指标 | 公开 ZIP/CSV，官方数据站 | 加密永续 K 线、metrics | 遵守官方条款；注明来源 |
| Binance Futures API | 实时/历史 | 官方 REST | 资金费率、持仓量、标记价格 | 限频；密钥不入库 |
| SSRN | 工作论文 | 网页/摘要；PDF 视许可 | 论文元数据、摘要、假设 | 不批量抓取；不默认存全文；尊重 robots/ToS |
| arXiv (q-fin) | 预印本 | 官方 API / OAI-PMH / 导出 | 元数据、摘要、PDF（许可允许时） | 遵守 arXiv API 条款与论文许可 |
| Papers With Backtest | 策略库 | 以官方提供的接口/导出为准 | 策略逻辑、代码参考 | 未授权不爬取；不复制/再分发代码 |
| Quantpedia | 策略百科 | 免费层人工；付费 API | 策略摘要、结构化规则 | 按订阅协议使用；不绕过付费墙 |
| NBER | 工作论文 | 官网/RSS/PDF | 经济逻辑、因子假设 | 尊重版权；仅内部研究 |
| Risk.net / JPM | 期刊/行业 | 机构订阅 | 元数据、摘要、方法参考 | 仅授权访问；不分发全文 |
| TradingView | 社区策略 | 手动导入/公开页面参考 | 开源策略逻辑、Pine 参考 | ToS 通常禁止批量抓取/再分发；只做人工导入 |
| 本地文件 | PDF/CSV/文本 | 用户上传 | 前期开发测试 | 用户自行保证授权 |

**统一原则**

- **优先官方 API/RSS/导出**；没有授权就不做自动化抓取。
- 只存**元数据 + 摘要 + 引用 + 必要片段**；全文存储需许可允许。
- 每个 Document 记录 `license_status`（`open` / `abstract_only` / `institutional` / `unknown`）。
- 来源可随时增删：`config/sources/*.yaml` + `SourceConnector` 注册。

### 2.1 来源配置示例

```yaml
id: arxiv_qfin
kind: preprint
enabled: true
connector: arxiv
base_url: https://export.arxiv.org/api/query
categories: [q-fin.PM, q-fin.TR, q-fin.ST]
rate_limit:
  requests_per_second: 0.33
  burst: 3
storage:
  metadata: true
  abstract: true
  full_text: license_dependent
  allowed_licenses: ["arXiv", "CC-BY", "CC-BY-SA"]
notes: "使用官方 API；遵守 arXiv 使用条款"
```

---

## 3. 数据分层

```text
data/
├── raw/                    # 原始文件，不可变；按来源/日期归档
│   ├── binance/
│   │   └── futures/um/klines/1d/BTCUSDT/2024/
│   └── uploads/
├── curated/                # 规范化 Parquet，双时间轴
│   ├── market=crypto_perp/frequency=1d/symbol=BTCUSDT/year=2024/part-*.parquet
│   └── market=cn_equity/frequency=1d/...
├── features/               # 因子值缓存（内容寻址）
│   └── factor=<spec_hash>/snapshot=<id>/...
├── snapshots/              # 快照清单
│   └── snap_2026_10_17/manifest.json
├── artifacts/              # 报告/图表/日志（也可放 MinIO）
└── holdout/                # 隔离样本，独立权限/加密
```

| 层 | 内容 | 可变性 | 访问 |
|---|---|---|---|
| raw | 下载的原始 ZIP/CSV/PDF | 只追加 | Data Worker |
| curated | 规范化、去重、PIT 字段 | 只追加（新分区/新版本） | 研究/验证 |
| features | 因子值 | 可重建 | 研究/验证 |
| snapshots | 清单与哈希 | 不可变 | 全部 |
| holdout | OOS 数据 | 只读、一次性挂载 | 金库服务 |

---

## 4. 双时间轴与 PIT

### 4.1 时间字段

每条 curated 记录至少包含：

| 字段 | 含义 |
|---|---|
| `event_time` | 事实发生时间（K 线开盘/收盘、财报报告期） |
| `available_at` | 该记录在现实世界可获得的时间 |
| `ingested_at` | 平台写入时间 |
| `source_id` / `source_version` | 来源与版本 |
| `snapshot_id` | 所属快照 |

**PIT 连接规则**：

```sql
-- 正确：只看决策时点之前已可获得的数据
WHERE available_at <= :decision_time

-- 错误：按报告期连接（典型未来函数）
WHERE period_end <= :decision_time
```

### 4.2 各市场的 `available_at` 规则

| 数据 | `event_time` | `available_at` |
|---|---|---|
| 日 K 线 | 交易日收盘 | 收盘后 + 交易所延迟（可配，默认 0–5 min） |
| 分钟 K 线 | bar close | bar close + 延迟 |
| 资金费率 | 结算时点 | 结算时点 + 延迟 |
| 持仓量/多空比 | 快照时点 | 快照时点 + 延迟 |
| 财报 | 报告期结束 | **公告日/公告时间**（不是报告期） |
| 指数成分 | 调整生效日 | 调整公告日（如适用） |
| 分红/拆股 | 除权日 | 公告日 |
| 宏观数据 | 统计期 | 实际发布时间 |

### 4.3 Universe 的 PIT

```sql
universe_membership (
  universe_id   text,
  symbol        text,
  valid_from    date,
  valid_to      date,
  as_of         timestamptz,
  rank_metric   numeric,
  source        text
)
```

- 加密：按滚动成交额/持仓量排名，排名只用 `available_at <= t` 的数据；每月/每周重排。
- A 股：指数成分按公告与生效日；退市标的保留历史，避免幸存者。
- 禁止：用当前 top100 列表回填 2020 年的 universe。

---

## 5. MarketAdapter 接口

```python
from datetime import datetime
from typing import Protocol, Sequence
import polars as pl

class FieldRef(Protocol):
    name: str
    source: str
    availability_lag_seconds: int

class MarketAdapter(Protocol):
    market: str                        # "crypto_perp" | "cn_equity"
    frequencies: Sequence[str]         # ["1m", "1h", "1d"]

    def calendar(self) -> "TradingCalendar":
        """交易日历、时区、结算时点。"""

    def universe(self, as_of: datetime, universe_id: str) -> list[str]:
        """返回 as_of 时点有效的标的列表（PIT）。"""

    def load_panel(
        self,
        fields: Sequence[FieldRef],
        start: datetime,
        end: datetime,
        universe: Sequence[str] | None = None,
        as_of: datetime | None = None,
    ) -> "Panel":
        """返回 MultiIndex/长表面板，只包含 available_at <= as_of 的记录。"""

    def labels(
        self,
        start: datetime,
        end: datetime,
        horizon: str,
        execution_delay: str = "1bar",
    ) -> "LabelPanel":
        """构造前向收益，处理分红/资金费率/停牌。"""

    def validate(self, panel: "Panel") -> "DataQualityReport":
        """市场特定的数据质量规则。"""
```

**实现清单**

| 市场 | 适配器 | 关键差异 |
|---|---|---|
| 加密永续 | `BinancePerpAdapter` | 24/7、资金费率、合约切换、USDT 计价 |
| A 股 | `CnEquityAdapter` | 交易日历、涨跌停、停牌、复权、财报公告日、成分股 |
| 美股 | `UsEquityAdapter` | 时区、拆股、退市、盘前盘后 |

---

## 6. 标签构造

### 6.1 时点定义

```text
decision_time  = t 收盘（信号可用）
execution_time = t + delay（默认下一 bar 开盘）
label_end      = execution_time + horizon
forward_return = P(label_end) / P(execution_time) - 1
```

三者写入 `LabelSpec`，并在报告中展示。**禁止**信号与成交使用同一收盘价而不声明。

### 6.2 收益调整

| 市场 | 调整 |
|---|---|
| 加密永续 | 价格收益 − 资金费率（按持仓方向）；考虑合约乘数 |
| A 股 | 复权价；分红；停牌日处理；涨跌停不可成交 |
| 美股 | 拆股、分红、退市收益 |

### 6.3 重叠标签

若 `horizon > frequency`，相邻标签重叠，IC/收益序列自相关：

- t 统计量用 Newey-West；
- CPCV 必须 Purge（删除与测试期标签重叠的训练样本）；
- 报告中注明重叠程度。

---

## 7. 数据质量检查

### 7.1 通用规则

| 检查 | 规则 | 级别 |
|---|---|---|
| 主键唯一 | `(symbol, event_time)` 不重复 | blocking |
| 时间单调 | 每个 symbol 时间递增 | blocking |
| 缺失 | 日历内缺失率 ≤ 阈值 | warning/blocking |
| OHLC 一致 | `low ≤ min(open, close) ≤ max(open, close) ≤ high` | blocking |
| 非负 | `volume ≥ 0`，价格 > 0 | blocking |
| 极端收益 | 单期 |收益| > 50%（加密可放宽） | warning |
| 无穷/NaN | 不允许无穷 | blocking |
| 时区 | 统一 UTC，交易日历单独处理 | blocking |
| 复权 | 复权因子连续、无未来信息 | blocking |

### 7.2 报告

```json
{
  "snapshot_id": "snap_...",
  "rows": 218400,
  "symbols": 100,
  "date_range": ["2020-01-01", "2025-12-31"],
  "blocking": 0,
  "warnings": 12,
  "issues": [
    {"code": "MISSING_BAR", "symbol": "XYZUSDT", "time": "2024-03-12", "detail": "gap 1d"}
  ],
  "checked_at": "2026-10-17T..."
}
```

**阻断规则**：存在 blocking 问题时，快照不可用于验证；Data Worker 修复/隔离后再生成新快照。

---

## 8. 数据快照

### 8.1 清单

```json
{
  "snapshot_id": "snap_2026_10_17_crypto_daily_v1",
  "market": "crypto_perp",
  "frequency": "1d",
  "start": "2020-01-01",
  "end": "2025-12-31",
  "created_at": "2026-10-17T08:00:00Z",
  "schema_version": "1.0",
  "files": [
    {"path": "curated/market=crypto_perp/frequency=1d/symbol=BTCUSDT/year=2024/part-0.parquet",
     "sha256": "...", "rows": 366}
  ],
  "row_counts": {"total": 218400, "by_symbol": {"BTCUSDT": 2192}},
  "source_versions": {"binance_public_data": "2026-10-16"},
  "quality_report_uri": "s3://.../quality.json",
  "manifest_hash": "sha256:..."
}
```

### 8.2 规则

- 快照一旦创建不可修改；数据修正 → 新快照。
- `snapshot_id` 进入所有 Trial、Backtest、ValidationRun、Report。
- IS 与 OOS 使用不同快照段，OOS 段在 `holdout/` 独立存放。
- 快照创建是 Data Worker 的 Step，有质量报告与人工确认（可配置）。

---

## 9. 因子值缓存

### 9.1 缓存键

```text
cache_key = sha256(
  spec_hash
  + snapshot_id
  + universe_hash
  + preprocess_hash
  + runtime_version
)
```

### 9.2 存储

- 每个因子/参数组合一个 Parquet：`features/factor=<spec_hash>/snapshot=<id>/params=<hash>/values.parquet`；
- 列：`symbol, timestamp, value`；
- 元数据：行数、有效截面、NaN 比例、计算耗时、代码/环境哈希。

### 9.3 失效

- 任何输入变化（代码、快照、universe、预处理）→ 新键；
- 不手工删缓存；用 TTL/配额清理最久未用；
- 缓存命中率进入监控指标。

---

## 10. 存储与查询

### 10.1 格式

- **Parquet**：curated/features/artifacts 的主格式，Snappy/Zstd 压缩。
- **DuckDB**：研究查询、聚合、join；可直接读 Parquet。
- **PostgreSQL**：元数据、任务、试验、指标；不存大面板。
- **MinIO/S3**：报告、图表、日志、PDF；内容寻址。

### 10.2 分区

```text
curated/market=<market>/frequency=<freq>/symbol=<symbol>/year=<yyyy>/part-*.parquet
```

- 加密 1m 数据按 symbol + year + month 分区；
- 日频可按 market + frequency + year 分区；
- 查询时先做分区裁剪，避免全量扫描。

### 10.3 容量估算（首期）

| 数据 | 规模 | 估算 |
|---|---|---|
| 100 标的 × 6 年日频 K 线 | ~22 万行 | < 100 MB |
| 100 标的 × 6 年日频 metrics | ~22 万行 | < 100 MB |
| 100 标的 × 6 年 1 分钟 K 线 | ~3.15 亿行 | 10–30 GB（Parquet） |
| 因子缓存 1000 个 | 每因子 ~22 万行 | 10–50 GB |
| 报告/图表 | — | < 10 GB |

---

## 11. 现有代码迁移

当前仓库已有：

```text
backend/downloader/feature_kline_downloader.py     # Binance K 线下载
backend/downloader/feature_metrics_downloader.py   # metrics 下载
backend/downloader/feature_kline_aggregator.py     # 1h → 4h/8h/1d 聚合
backend/downloader/feature_metrics_aggregator.py
backend/downloader/feature_data_check.py
backend/downloader/top100_symbols_downloader.py
backend/config/config.py
backend/utils/utils.py
backend/strategy/ema_strategy.py                   # 时序策略示例
```

### 11.1 迁移映射

| 现有 | 目标 | 说明 |
|---|---|---|
| `feature_kline_downloader.py` | `quant/data/sources/binance/klines.py` | 保留下载逻辑，增加 `available_at`、manifest、重试/限速 |
| `feature_metrics_downloader.py` | `quant/data/sources/binance/metrics.py` | 同上 |
| `feature_kline_aggregator.py` | `quant/data/pipeline/aggregate.py` | 增加缺口检查、时区、分区写入 |
| `feature_metrics_aggregator.py` | 同上 | — |
| `feature_data_check.py` | `quant/data/quality.py` | 扩展为规则引擎 |
| `top100_symbols_downloader.py` | `quant/data/universes/binance_topn.py` | 改为 PIT universe |
| `config/config.py` | `backend/config/settings.py` + YAML | 环境变量；密钥分离 |
| `utils.py` | `quant/data/io.py` | 去掉全局 config 依赖 |
| `strategy/ema_strategy.py` | `examples/time_series/ema.py` | 作为回归测试样例，不进入生产库 |

### 11.2 迁移原则

1. **先包一层**：新代码通过适配器调用旧函数，跑通现有数据与 EMA 回归测试。
2. **再替换**：逐步把下载/聚合逻辑移入 `quant/data`，旧文件保留 shim。
3. **回归基线**：对同一份原始数据，迁移前后因子值/回测结果在容差内一致。
4. **不要一次性重写**：数据代码最容易引入静默错误。

### 11.3 现有数据字典

**K 线（Binance USDT-M 永续）**

| 字段 | 含义 |
|---|---|
| `open_time` | bar 开盘时间（ms） |
| `open/high/low/close` | OHLC |
| `volume` | 基础币成交量 |
| `close_time` | bar 收盘时间（ms） |
| `quote_volume` | USDT 成交额 |
| `count` | 成交笔数 |
| `taker_buy_volume` | 主动买入量 |
| `taker_buy_quote_volume` | 主动买入额 |

**Metrics**

| 字段 | 含义 |
|---|---|
| `create_time` | 快照时间 |
| `symbol` | 交易对 |
| `sum_open_interest` | 总持仓量（基础币） |
| `sum_open_interest_value` | 持仓总价值 |
| `count_toptrader_long_short_ratio` | 大户账户数多空比 |
| `sum_toptrader_long_short_ratio` | 大户持仓量多空比 |
| `count_long_short_ratio` | 全体账户数多空比 |
| `sum_taker_long_short_vol_ratio` | 吃单买卖量比 |

> 现有文档提示：2022-03-16 之前的多空比数据不稳定，建议在数据质量规则中标记该区间，或从样本中剔除。

---

## 12. 新市场接入清单

- [ ] 实现 `MarketAdapter`（calendar/universe/load_panel/labels/validate）
- [ ] 定义字段字典与 `available_at` 规则
- [ ] 建立 PIT universe（成分/排名历史）
- [ ] 处理公司行为/合约切换/资金费率
- [ ] 编写数据质量规则（市场特定）
- [ ] 生成首个数据快照与质量报告
- [ ] 用已知因子/策略做回归基线
- [ ] 创建 `ValidationProfile`（阈值 + 状态定义）
- [ ] 标注许可与来源
- [ ] 加入负对照测试（随机/未来污染）

---

## 13. 数据平台反模式

| 反模式 | 问题 | 正确做法 |
|---|---|---|
| 直接读最新 CSV | 不可复现 | 绑定快照 |
| 用报告期连接财报 | 未来函数 | 用公告日 `available_at` |
| 用当前 top100 回填历史 | 幸存者偏差 | PIT universe |
| 全样本标准化 | 未来函数 | 截面/滚动标准化 |
| 手工删缓存 | 结果漂移 | 内容寻址 + 版本 |
| 把大面板塞进 PostgreSQL | 膨胀/慢 | Parquet + DuckDB |
| 混用 UTC 与交易所时区 | 时点错位 | 统一 UTC + 日历 |
| 忽略停牌/涨跌停 | 回测不可交易 | 市场适配器处理 |
| 抓取付费全文 | 合规风险 | 元数据/摘要/授权 |
