# 09 · 路线图与实施计划

> 原则：先把“统计内核 + 数据契约”做对，再叠加 Agent 和 H5；每个里程碑都有可验收的纵向切片。  
> 上游：[README](README.md)

---

## 1. 实施策略

1. **纵向切片**：每个阶段都交付“从输入到报告”的可运行闭环，而不是先铺满所有模块。
2. **先内核后界面**：验证引擎与数据契约不稳定时，不做复杂 UI/Agent。
3. **先本地后外部**：先用本地 PDF/CSV 跑通，再接 arXiv/SSRN 等来源。
4. **先加密后 A 股**：沿用现有 Binance 数据，降低首期数据接入风险；A 股作为第二个适配器。
5. **先单机后扩展**：Docker Compose 单机足够；队列/存储接口预留升级空间。
6. **每阶段校准统计**：负对照测试是发布门禁，不是可选项。

---

## 2. 里程碑总览

```mermaid
flowchart LR
    M0["M0 设计冻结<br/>1-2 周"] --> M1["M1 数据+因子内核<br/>2-3 周"]
    M1 --> M2["M2 验证引擎 G0-G4<br/>3-4 周"]
    M2 --> M3["M3 API+队列+H5<br/>3-4 周"]
    M3 --> M4["M4 Agent 挖掘闭环<br/>3-4 周"]
    M4 --> M5["M5 G5-G7+金库+硬化<br/>3-4 周"]
    M5 --> M6["M6 多市场/扩展<br/>持续"]
```

> 工期为单人全职的粗略估算，含测试与文档；实际取决于数据接入与 LLM 调试。

---

## 3. M0 · 设计冻结与工程骨架（1–2 周）

### 交付物

- [x] 架构设计文档（本套 docs）
- [ ] 确认第 9 节关键决策（市场/部署/LLM/用户）
- [ ] 冻结三个契约：
  - [x] `FactorSpec v1`（Pydantic 契约 + JSON Schema + 示例）
  - [x] `ValidationProfile v1`（Pydantic 契约 + JSON Schema + 示例）
  - [ ] 事件协议 v1（随 M3 API 冻结）
- [x] 研究内核骨架：`backend/quant/`、`pyproject.toml`、ruff、mypy、pytest、pre-commit
- [ ] `backend/app/`、`backend/agents/`、`backend/workers/`、`webui/` 初始化（M3/M4）
- [x] `deploy/docker-compose.yml`（Postgres/Redis 开发依赖）
- [x] CI：lint + typecheck + unit + schema 漂移检查
- [x] ADR 目录与首批 ADR（`docs/adr/`）
- [x] `.env.example`；配置加载规范随 API 实现落地

### 验收标准

- 新成员能按 README 启动开发环境；
- `pytest` 通过（至少契约/DSL 解析的单测）；
- 三个契约有 Schema 文件与示例；
- 设计评审记录归档。

### 风险

- 过度设计：只冻结必要契约，细节留到实现；
- 技术选型争议：以 ADR 记录，不拖延。

---

## 4. M1 · 数据平台与因子内核（2–3 周）

### 交付物

- [x] `MarketAdapter` 接口 + `BinancePerpAdapter`（首个实现，本地 Parquet）
- [ ] 现有 downloader/aggregator 迁移或包装
- [x] 双时间轴字段（`event_time/available_at/ingested_at`）
- [ ] PIT universe（top N 成交额，按决策时点）
- [ ] 数据快照生成 + manifest + 质量报告
- [ ] Parquet/DuckDB 存储与分区
- [x] `FactorSpec` 解析器 + AST + 20+ 算子
- [x] `FactorRuntime`（Polars）与内容寻址缓存
- [x] 标签构造（执行延迟 + horizon）
- [x] CLI：`quant factor compute`（`quant snapshot create` 待实现）
- [ ] 黄金数据集（固定小样本 + 期望输出）

### 验收标准

- 用现有 Binance 数据生成一个快照，质量报告无 blocking；
- 3 个示例因子（动量、波动率、成交量）可计算并缓存；
- PIT 回放测试通过（抽样 ≥ 20 时点）；
- 同一 spec + snapshot 重算结果一致（哈希/容差）；
- 现有 EMA 策略可读取新数据格式（回归基线）。

### 风险

- 数据下载慢/限频：先做小样本，后台补齐；
- 聚合逻辑静默错误：黄金数据集 + 对账；
- PIT universe 复杂：先做简单滚动排名，逐步完善。

---

## 5. M2 · 验证引擎 G0–G4（3–4 周）

### 交付物

- [ ] G0：数据质量、PIT 回放、AST 审计、负对照
- [ ] G1：IC/Rank IC/ICIR/胜率/Newey-West/子期/衰减
- [ ] G2：分层、单调性、多空、换手、成本
- [ ] G3：参数网格/高原、状态分组、置换、Bootstrap、成本敏感性
- [ ] G4：与因子库相关性、正交化、残差 IC
- [ ] `GateResult` JSON + 报告 JSON
- [ ] 指标单元测试与统计校准（噪声/已知信号）
- [ ] CLI：`quant validate --factor ... --profile ...`

### 验收标准

- 随机因子在 G1–G4 的通过率接近名义水平；
- 已知有效因子（如动量）能通过 G1–G4；
- 未来污染因子被 G0 捕获；
- 参数尖峰因子被 G3 判失败；
- 报告包含样本量、阈值、失败原因、图表数据；
- 单因子 100×5 年日频计算 < 10s，G1+G2 < 30s。

### 风险

- 统计实现错误：用合成数据校准，逐公式对照；
- 阈值不合适：先记录分布，不急于冻结；
- 计算慢：Polars 向量化 + 缓存。

---

## 6. M3 · 后端 API、队列与 H5 监控（3–4 周）

### 交付物

- [ ] FastAPI 骨架、鉴权、错误格式、OpenAPI
- [ ] PostgreSQL 模型 + Alembic 迁移
- [ ] Redis + Celery 队列、Worker 池、调度器
- [ ] 任务/步骤状态机、租约、重试、取消
- [ ] 事件表 + SSE（含回放/心跳/断线）
- [ ] REST：tasks/steps/gates/factors/artifacts
- [ ] H5 P0：登录、任务列表、任务详情、SSE、审批、错误/空状态
- [ ] E2E：创建任务 → 模拟 Worker → 进度 → 完成
- [ ] 队列/Worker 监控页（P1）

### 验收标准

- 断网重连后事件不丢（`Last-Event-ID`）；
- 任务暂停/恢复/取消状态正确；
- 审批后下游步骤自动推进；
- H5 在 375px/4G 下首屏 < 2s；
- 100 条任务的列表滚动流畅；
- API P95 < 300ms（本地）。

### 风险

- SSE/移动端后台挂起：轮询兜底 + 通知；
- Celery 状态一致性：DB 为事实来源 + 幂等；
- 前端范围膨胀：只做 P0/P1，复杂编辑后置。

---

## 7. M4 · Agent 挖掘闭环（3–4 周）

### 交付物

- [ ] LLM Gateway（路由、结构化输出、预算、缓存、计量）
- [ ] 角色：Scout、Extractor、Implementer、Static Auditor、Validator、Critic、Reporter
- [ ] 策略模板库 v1（截面排序、时序阈值、事件驱动）
- [ ] Tool Registry + 10+ 工具
- [ ] 沙箱 Runner（无网络、资源限制、AST 白名单）
- [ ] 本地 PDF 上传 → 提取假设 → 生成 DSL → G0–G4
- [ ] 提示词版本化与回归测试
- [ ] 提示注入测试集
- [ ] H5：Agent 时间线、工具调用展示、成本

### 验收标准

- 上传一篇本地论文，端到端产出至少 1 个因子与 G0–G4 报告；
- Agent 生成的代码 100% 经沙箱与 AST 检查；
- 引用可在原文定位；
- 工具调用/成本/失败可在 H5 回放；
- 提示注入测试全部拒绝；
- 任务预算超限会暂停并通知。

### 风险

- 论文理解偏差：引用校验 + Critic + 人工门槛；
- LLM 成本：预算、缓存、小模型分流；
- 代码生成不稳定：DSL 优先，模板约束；
- 沙箱性能：镜像预热、限制并发。

---

## 8. M5 · G5–G7、金库与生产硬化（3–4 周）

### 交付物

- [ ] Trial Registry 完整实现（预登记、族、失败保留）
- [ ] G5：BH-FDR、PBO/CSCV、N_eff、DSR
- [ ] G6：CPCV + Purge/Embargo、WFO、蒙特卡洛、双引擎对账
- [ ] G7：OOS 金库、一次性 token、哈希链账本、审批流
- [ ] 因子族与 OOS 消耗治理
- [ ] 审计日志、复现清单、`reproduce` 命令
- [ ] 安全测试（沙箱逃逸、SSRF、权限）
- [ ] 备份/恢复演练
- [ ] 生产 Compose + Nginx + TLS + 监控

### 验收标准

- 纯噪声策略族被 PBO/DSR 拒绝；
- 已知有效策略能通过 G6（合成数据校准）；
- OOS 只能解锁一次，重复请求被拒绝；
- 账本链可校验，审批不可抵赖；
- 报告可复现（重算指标一致）；
- 沙箱逃逸测试全部失败（即攻击被阻断）；
- 故障恢复后任务可继续/重试。

### 风险

- PBO/CPCV 计算量大：S=10 起步，缓存 mask，最终验证再 S=16；
- DSR 实现细节：用已知案例校准；
- OOS 治理复杂：先单用户 + 强制确认，再多人审批；
- 安全硬化耗时：按清单逐项验收。

---

## 9. M6 · 多市场与扩展（持续）

### 方向

- A 股适配器：PIT 财务、成分股、行业、复权、涨跌停、停牌；Barra/FF 因子库。
- 美股适配器。
- 更多来源连接器（官方 API/RSS）。
- 多用户/RBAC。
- Web Push / PWA。
- 分布式 Worker / Kubernetes。
- 因子组合与策略池管理。
- 更丰富的报告与归因。

### 验收标准（A 股）

- PIT 回放通过（财报公告日、成分股调整）；
- 已知 A 股因子（如 12-1 动量、价值）通过 G1–G4；
- 幸存者偏差测试通过；
- 行业/市值中性化正确；
- 与 Barra/FF 相关性/正交化结果合理。

---

## 10. 第一 Sprint 建议（2 周）

### Week 1

- 冻结 `FactorSpec v1` + JSON Schema + 示例；
- 搭建 `backend/quant/` 骨架与 CI；
- 定义数据面板格式与 `available_at` 规则；
- 实现 DSL 解析 + 5 个基础算子（`ts_mean`, `ts_return`, `cs_rank`, `cs_zscore`, `ts_std`）；
- 读取现有 Binance 数据为统一 Panel。

### Week 2

- 实现因子计算与缓存；
- 实现 G1（Rank IC/ICIR/t 值）；
- 用 3 个示例因子跑通；
- 生成第一份 JSON 报告；
- 写负对照测试（随机因子应失败）。

### Sprint 验收

```bash
python -m quant.cli factor compute \
  --spec examples/momentum.yaml \
  --snapshot snap_dev \
  --output out/

python -m quant.cli validate \
  --factor examples/momentum.yaml \
  --profile crypto_perp_daily_v1 \
  --gates G0,G1,G2 \
  --output out/report.json
```

- 输出可读报告；
- 随机因子与动量因子的结果有明显区分；
- 计算可重复（同输入同输出）。

---

## 11. 风险登记

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 统计实现错误导致假阳性 | 中 | 高 | 合成数据校准、负对照、代码评审 |
| 数据源合规问题 | 中 | 高 | 官方 API/元数据优先、许可状态、人工审核 |
| PIT 数据缺失（尤其 A 股） | 高 | 高 | 先加密后 A 股；数据供应商评估 |
| LLM 成本/不稳定 | 中 | 中 | 预算、缓存、小模型分流、结构化输出 |
| 范围膨胀 | 高 | 中 | 里程碑门禁、P0/P1 优先级 |
| 沙箱逃逸 | 低 | 高 | 无网络、非 root、只读、定期演练 |
| OOS 泄露 | 中 | 高 | 金库、一次性 token、账本、审批分离 |
| 计算性能不足 | 中 | 中 | Polars、缓存、并发控制、S=10 起步 |
| 前端实时性/弱网 | 中 | 低 | SSE + 轮询兜底 + 增量同步 |
| 单人维护负担 | 高 | 中 | 先单机、少依赖、接口清晰、文档先行 |

---

## 12. 开放问题

| # | 问题 | 影响 | 建议 |
|---|---|---|---|
| Q1 | 首期只做加密，还是同步做 A 股？ | 数据接入/验证 Profile | 先加密，A 股 M6 |
| Q2 | LLM 供应商与预算？ | Agent 设计/成本 | Claude 默认，接口抽象 |
| Q3 | 部署在本地还是云？ | 队列/存储/安全 | 本地 Compose 起步 |
| Q4 | 是否需要多用户/团队？ | 权限/审计 | 首期单用户，预留 RBAC |
| Q5 | OOS 数据段如何定义？ | 金库/治理 | 按市场+半年/一年，冻结后不用 |
| Q6 | 是否接入商业数据（Wind/聚源/Barra）？ | A 股 PIT 质量 | M6 前评估 |
| Q7 | 因子晋升后的去向？ | 产品边界 | 首期只输出报告/因子库，不接实盘 |
| Q8 | 是否需要 GPU？ | 因子计算/LLM | 首期不需要；ML 因子后评估 |

---

## 13. 完成定义（Definition of Done）

一个功能/里程碑完成需满足：

- [ ] 代码通过 lint/typecheck/unit/integration；
- [ ] 统计相关有校准测试或黄金数据；
- [ ] 契约（Schema/事件/API）有文档与示例；
- [ ] 错误路径有测试与可读错误码；
- [ ] 关键操作有审计日志；
- [ ] 可复现清单完整；
- [ ] 前端有 loading/empty/error 状态；
- [ ] 更新相关设计文档；
- [ ] 演示通过（端到端可运行）。

---

## 14. 建议的评审节点

| 节点 | 参与 | 产出 |
|---|---|---|
| 设计评审 | 架构/研究/前端 | 冻结契约、确认范围 |
| M1 评审 | 研究 | 数据快照/因子结果可复现 |
| M2 评审 | 研究/统计 | 负对照通过、阈值校准报告 |
| M3 评审 | 前端/后端 | H5 演示、SSE 稳定性 |
| M4 评审 | 研究/安全 | Agent 端到端、注入测试 |
| M5 评审 | 全员 | OOS 演练、安全清单、上线 |
