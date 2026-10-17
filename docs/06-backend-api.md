# 06 · 后端 API 与任务编排

> 目标：定义前后端契约、任务队列、事件推送与错误处理。  
> 上游：[系统架构](01-system-architecture.md)　下游：[H5 前端](07-frontend-h5.md)

---

## 1. API 设计原则

1. **REST + SSE**：查询/操作走 REST，实时进度走 Server-Sent Events。
2. **资源化**：任务、步骤、因子、试验、验证、报告、金库都是资源。
3. **幂等**：所有创建/提交类接口支持 `Idempotency-Key`。
4. **游标分页**：列表使用 `cursor`，避免移动端翻页错位。
5. **结构化错误**：统一 `code/message/details/request_id`。
6. **版本化**：路径 `/api/v1`；破坏性变更升版本。
7. **OpenAPI 优先**：Pydantic Schema 自动生成文档；前端从 OpenAPI 生成类型。

---

## 2. 认证与权限

### 2.1 首期（单用户）

```http
Authorization: Bearer <token>
```

- Token 从 `.env`/Secret Manager 读取，支持多个 token（个人/CI）。
- CLI 使用 `X-API-Key`（等价）。
- 所有写操作记录 `audit_log`。

### 2.2 后续（多用户）

- OAuth2/OIDC；
- RBAC：`viewer` / `researcher` / `approver` / `admin`；
- 资源级隔离：任务、因子、报告按 `owner/team` 过滤；
- G7 解锁需要 `approver` 角色。

### 2.3 权限矩阵（首期简化）

| 操作 | viewer | researcher | approver |
|---|---|---|---|
| 查看任务/报告 | ✓ | ✓ | ✓ |
| 创建任务/因子 | — | ✓ | ✓ |
| 暂停/取消自己的任务 | — | ✓ | ✓ |
| 审批 G0/G5 | — | — | ✓ |
| 审批 OOS 解锁 | — | — | ✓ |
| 修改来源/阈值 | — | — | ✓ |

---

## 3. 资源与端点总览

```text
/api/v1
├── /tasks
├── /steps
├── /factors
├── /trials
├── /validation-runs
├── /gates
├── /reports
├── /holdouts
├── /sources
├── /documents
├── /hypotheses
├── /artifacts
├── /queue
├── /workers
├── /notifications
└── /health
```

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/tasks` | 创建研究任务 |
| GET | `/tasks` | 任务列表（状态/市场/时间过滤） |
| GET | `/tasks/{task_id}` | 任务详情（含步骤摘要、计数、预算） |
| POST | `/tasks/{task_id}/pause` | 暂停 |
| POST | `/tasks/{task_id}/resume` | 恢复 |
| POST | `/tasks/{task_id}/cancel` | 取消 |
| GET | `/tasks/{task_id}/steps` | 步骤列表 |
| GET | `/tasks/{task_id}/events` | **SSE** 实时事件 |
| GET | `/tasks/{task_id}/timeline` | 事件回放（非 SSE） |
| GET | `/tasks/{task_id}/artifacts` | 任务产物 |
| GET | `/steps/{step_id}` | 步骤详情 |
| GET | `/steps/{step_id}/logs` | 日志（游标分页） |
| POST | `/steps/{step_id}/retry` | 重试失败步骤 |
| GET | `/factors` | 因子列表 |
| POST | `/factors` | 手动创建因子 |
| GET | `/factors/{factor_id}` | 因子详情 |
| GET | `/factors/{factor_id}/versions` | 版本列表 |
| GET | `/factors/{factor_id}/versions/{version}` | 版本详情 |
| GET | `/factors/{factor_id}/trials` | 该因子的试验 |
| GET | `/trials/{trial_id}` | 试验详情 |
| GET | `/validation-runs/{run_id}` | 验证详情 |
| GET | `/validation-runs/{run_id}/gates` | 门槛结果 |
| GET | `/validation-runs/{run_id}/report` | 报告 JSON |
| GET | `/gates/{gate_id}` | 门槛详情 |
| POST | `/gates/{gate_id}/decision` | 人工审批（approve/reject） |
| GET | `/reports/{report_id}` | 报告 |
| GET | `/reports/{report_id}/export` | 导出 PDF/JSON |
| GET | `/holdouts` | 隔离样本列表 |
| POST | `/holdouts/{segment_id}/unlock-requests` | 申请解锁 |
| GET | `/holdout-unlock-requests` | 解锁申请列表 |
| POST | `/holdout-unlock-requests/{id}/approve` | 批准 |
| POST | `/holdout-unlock-requests/{id}/reject` | 拒绝 |
| GET | `/sources` | 来源列表 |
| POST | `/sources` | 新增来源 |
| PATCH | `/sources/{source_id}` | 启停/改配置 |
| POST | `/sources/{source_id}/sync` | 触发同步 |
| GET | `/documents` | 文档列表 |
| GET | `/documents/{document_id}` | 文档详情（含许可状态） |
| GET | `/hypotheses` | 假设列表 |
| GET | `/artifacts/{artifact_id}` | 产物元数据 |
| GET | `/artifacts/{artifact_id}/download` | 获取签名下载 URL |
| GET | `/queue/stats` | 队列深度/吞吐 |
| GET | `/workers` | Worker 状态 |
| GET | `/notifications` | 通知 |
| POST | `/notifications/{id}/read` | 标记已读 |
| GET | `/health` | 健康检查 |
| GET | `/config/profiles` | 可用验证配置 |

---

## 4. 任务 API

### 4.1 创建任务

```http
POST /api/v1/tasks
Idempotency-Key: 7d3c...
Content-Type: application/json
```

```json
{
  "title": "加密市场短期动量因子",
  "goal": "从 arXiv/SSRN 近期论文中挖掘 1-4 周动量类因子，完成 G0-G6 验证",
  "market": "crypto_perp",
  "scope": "cross_sectional",
  "profile_id": "crypto_perp_daily_v1",
  "sources": ["arxiv_qfin", "ssrn", "local_upload"],
  "universe_id": "binance_top100_volume",
  "budget": {
    "tokens": 2000000,
    "usd": 20,
    "max_trials": 100,
    "max_hours": 6
  },
  "human_gates": ["G0", "G5", "G7"],
  "priority": 5,
  "metadata": {"requester": "niefy"}
}
```

响应 `201`：

```json
{
  "id": "tsk_01J9...",
  "status": "queued",
  "progress": 0,
  "created_at": "2026-10-17T10:00:00Z",
  "steps": [
    {"id": "stp_01", "key": "scout", "status": "pending", "depends_on": []},
    {"id": "stp_02", "key": "extract", "status": "pending", "depends_on": ["stp_01"]},
    {"id": "stp_03", "key": "implement", "status": "pending", "depends_on": ["stp_02"]},
    {"id": "stp_04", "key": "g0_audit", "status": "pending", "depends_on": ["stp_03"]},
    {"id": "stp_05", "key": "g1_ic", "status": "pending", "depends_on": ["stp_04"]},
    {"id": "stp_06", "key": "g2_quantile", "status": "pending", "depends_on": ["stp_05"]},
    {"id": "stp_07", "key": "g3_robust", "status": "pending", "depends_on": ["stp_06"]},
    {"id": "stp_08", "key": "g4_redundancy", "status": "pending", "depends_on": ["stp_07"]},
    {"id": "stp_09", "key": "g5_group", "status": "pending", "depends_on": ["stp_08"]},
    {"id": "stp_10", "key": "g6_strategy", "status": "pending", "depends_on": ["stp_09"]},
    {"id": "stp_11", "key": "g7_holdout", "status": "pending", "depends_on": ["stp_10"]},
    {"id": "stp_12", "key": "report", "status": "pending", "depends_on": ["stp_11"]}
  ]
}
```

### 4.2 任务详情

```json
{
  "id": "tsk_01J9...",
  "title": "加密市场短期动量因子",
  "status": "running",
  "progress": 0.42,
  "current_step": {
    "id": "stp_06",
    "key": "g2_quantile",
    "name": "G2 分层组合",
    "status": "running",
    "progress": 0.6,
    "message": "计算 5 分组多空收益"
  },
  "counts": {
    "sources_discovered": 12,
    "documents_parsed": 5,
    "hypotheses": 3,
    "factors": 2,
    "trials": 18,
    "gates_passed": 2,
    "gates_failed": 0
  },
  "budget": {
    "tokens_used": 430000,
    "tokens_limit": 2000000,
    "usd_used": 4.2,
    "usd_limit": 20,
    "trials_used": 18,
    "trials_limit": 100
  },
  "snapshot_id": "snap_2026_10_17_crypto_daily_v1",
  "profile_id": "crypto_perp_daily_v1",
  "created_at": "2026-10-17T10:00:00Z",
  "started_at": "2026-10-17T10:00:05Z",
  "finished_at": null,
  "error": null
}
```

### 4.3 暂停/恢复/取消

```http
POST /tasks/{task_id}/pause
POST /tasks/{task_id}/resume
POST /tasks/{task_id}/cancel
```

- 暂停：不再派发新 Step；运行中的 Step 允许完成或按 `force` 终止。
- 取消：运行中 Step 收到取消信号；已产生产物保留。
- 所有操作返回 `202 Accepted` + 当前状态。

---

## 5. SSE 事件协议

### 5.1 连接

```http
GET /api/v1/tasks/{task_id}/events
Accept: text/event-stream
Last-Event-ID: 12345
Authorization: Bearer <token>
```

### 5.2 帧格式

```text
id: 12346
event: step.progress
data: {"task_id":"tsk_...","step_id":"stp_06","percent":60,"message":"计算 5 分组多空收益","ts":"2026-10-17T10:12:00Z"}

: ping

id: 12347
event: gate.result
data: {"task_id":"tsk_...","gate_id":"G2","status":"failed","metrics":{"monotonicity":0.31},"ts":"..."}
```

### 5.3 事件类型

| `event` | 触发 | 关键字段 |
|---|---|---|
| `task.created` | 任务创建 | task_id |
| `task.status` | 状态变化 | status, message |
| `task.progress` | 总体进度 | percent |
| `step.started` | Step 开始 | step_id, key, name |
| `step.progress` | Step 进度 | step_id, percent, message |
| `step.log` | 日志行 | level, message, stream |
| `step.completed` | Step 完成 | step_id, status, artifact_ids |
| `step.failed` | Step 失败 | step_id, error_code, retryable |
| `agent.message` | Agent 过程摘要 | role, text |
| `agent.tool_call` | 工具调用 | tool, args_summary |
| `agent.tool_result` | 工具结果 | tool, status, summary |
| `llm.usage` | Token/成本 | model, tokens, cost_usd |
| `gate.result` | 门槛结果 | gate_id, status, metrics |
| `artifact.created` | 产物生成 | artifact_id, media_type, name |
| `trial.registered` | 试验登记 | trial_id, factor_id, params |
| `human.required` | 需要审批 | gate_id, summary, actions |
| `notification` | 通知 | type, payload |
| `task.completed` | 任务完成 | status, report_id |
| `heartbeat` | 心跳 | ts |

### 5.4 回放与断线

- 服务端先返回 `snapshot` 事件（当前任务/步骤状态），再回放 `seq > Last-Event-ID` 的事件；
- 若 `Last-Event-ID` 过旧（超出保留窗口），返回 `snapshot` 并提示 `reset: true`；
- 客户端指数退避重连（1s, 2s, 4s… 最大 30s），恢复后自动续传；
- 心跳每 15s；60s 无数据视为断线。

### 5.5 轮询兜底

移动端后台可能挂起 SSE。提供：

```http
GET /api/v1/tasks?updated_since=2026-10-17T10:00:00Z&limit=50
```

H5 在前台恢复时先拉一次增量，再重连 SSE。

---

## 6. 因子与报告 API

### 6.1 因子列表

```http
GET /factors?market=crypto_perp&status=candidate&scope=cross_sectional&limit=20&cursor=...
```

```json
{
  "items": [
    {
      "id": "fac_7f3a2c",
      "name": "crypto_momentum_20d",
      "market": "crypto_perp",
      "scope": "cross_sectional",
      "version": 1,
      "status": "candidate",
      "latest_verdict": "g1_g4_passed",
      "rank_ic": 0.031,
      "sharpe": 1.1,
      "updated_at": "..."
    }
  ],
  "next_cursor": "eyJpZCI6..."
}
```

### 6.2 验证报告

```http
GET /validation-runs/{run_id}/report
```

返回 [04-validation-pipeline.md](04-validation-pipeline.md) 第 15 节定义的报告 JSON。

### 6.3 报告导出

```http
GET /reports/{report_id}/export?format=pdf
```

- 返回 `302` 到签名 URL，或直接流式下载；
- PDF 由 Report Worker 预生成并缓存；
- JSON 永远可用，PDF 可能异步生成（返回 202 + `report.export_ready` 事件）。

### 6.4 人工审批

```http
POST /api/v1/gates/{gate_id}/decision
```

```json
{
  "decision": "approve",
  "reason": "已核对 PIT 回放与试验族完整性",
  "comment": "允许进入 G5"
}
```

响应：

```json
{
  "gate_id": "gat_...",
  "status": "passed",
  "decided_by": "niefy",
  "decided_at": "2026-10-17T11:00:00Z"
}
```

**规则**

- 只有 `waiting_human` 状态的 Gate 可审批；
- `reject` 后任务进入失败/终止，可在新任务中重试；
- 审批不可撤销，只能追加新记录；
- 所有审批写 `audit_log`。

---

## 7. OOS 金库 API

### 7.1 查询

```http
GET /holdouts
```

```json
{
  "items": [
    {
      "id": "hld_2026H2_crypto",
      "market": "crypto_perp",
      "start": "2026-07-01",
      "end": "2026-12-31",
      "status": "sealed",
      "consumed_by": null,
      "manifest_hash": "sha256:..."
    }
  ]
}
```

### 7.2 申请解锁

```http
POST /holdouts/{segment_id}/unlock-requests
```

```json
{
  "validation_run_id": "val_...",
  "reason": "G0-G6 全部通过，代码与环境已冻结",
  "frozen_manifest": {
    "git_commit": "abc123",
    "container_digest": "sha256:...",
    "profile_hash": "sha256:...",
    "family_id": "fam_..."
  }
}
```

服务端校验：

- 该 `validation_run` 的 G0–G6 均通过；
- `family_id` 未消耗过该 OOS 段；
- 冻结清单与实际环境一致；
- 请求人/审批人权限。

### 7.3 批准/拒绝

```http
POST /holdout-unlock-requests/{id}/approve
POST /holdout-unlock-requests/{id}/reject
```

批准后：

- 生成一次性 token（明文只返回一次）；
- 创建 `holdout_unlocks` 记录与哈希链；
- 触发 `g7_holdout` Step；
- 执行完成后 `status=consumed`。

**安全要求**

- token 只存哈希；
- token 绑定 `validation_run_id` + `segment_id` + 过期时间；
- 使用后立即失效；
- 重复请求返回 `409 HOLDOUT_ALREADY_CONSUMED`。

---

## 8. 错误格式与错误码

### 8.1 格式

```json
{
  "error": {
    "code": "GATE_NOT_PENDING",
    "message": "该门槛不处于待审批状态",
    "details": {"gate_id": "gat_...", "status": "passed"},
    "request_id": "req_01J..."
  }
}
```

### 8.2 错误码

| HTTP | code | 含义 |
|---|---|---|
| 400 | `INVALID_ARGUMENT` | 参数校验失败 |
| 401 | `UNAUTHORIZED` | 缺少/无效 token |
| 403 | `FORBIDDEN` | 权限不足 |
| 404 | `TASK_NOT_FOUND` / `FACTOR_NOT_FOUND` / ... | 资源不存在 |
| 409 | `IDEMPOTENCY_CONFLICT` | 幂等键复用但请求不同 |
| 409 | `GATE_NOT_PENDING` | 门槛状态不允许审批 |
| 409 | `HOLDOUT_ALREADY_CONSUMED` | OOS 已消耗 |
| 409 | `TASK_STATE_CONFLICT` | 非法状态流转 |
| 422 | `SCHEMA_VALIDATION_FAILED` | 结构校验失败 |
| 429 | `RATE_LIMITED` | 限流 |
| 500 | `INTERNAL_ERROR` | 未预期错误（含 request_id） |
| 503 | `QUEUE_UNAVAILABLE` | 队列/Worker 不可用 |

### 8.3 错误处理原则

- 不把堆栈/SQL/路径返回给客户端；
- 可重试错误返回 `retryable: true` 与 `retry_after_ms`；
- Agent/Step 错误保留结构化 `error_code`，H5 可展示；
- 所有 5xx 记录 `request_id` 与 trace_id。

---

## 9. 分页、过滤、排序

### 9.1 游标分页

```http
GET /tasks?status=running,failed&market=crypto_perp&limit=20&cursor=eyJpZCI6...
```

```json
{
  "items": [],
  "next_cursor": null,
  "has_more": false
}
```

- `cursor` 是不透明字符串（base64 编码的排序键）；
- 默认 `limit=20`，最大 100；
- 排序默认 `created_at desc`；
- 支持 `updated_since` 用于增量同步。

### 9.2 通用过滤

| 参数 | 适用 | 说明 |
|---|---|---|
| `status` | tasks/factors/trials | 逗号分隔多值 |
| `market` | tasks/factors | — |
| `scope` | factors | cross_sectional/time_series |
| `profile_id` | tasks/trials | — |
| `family_id` | trials | — |
| `updated_since` | tasks | ISO8601 |
| `q` | factors/documents | 名称/标题模糊搜索 |

---

## 10. 任务队列与 Worker

### 10.1 拓扑

```text
API → PostgreSQL（任务/步骤）
    → outbox → dispatcher → Redis（Celery broker + Pub/Sub 事件）
                              ├─ q.agent
                              ├─ q.data
                              ├─ q.factor
                              ├─ q.validation
                              ├─ q.backtest
                              └─ q.report
Worker → 领取 Step → 执行 → 写结果/事件 → ack
```

### 10.2 调度器

- 单实例（Redis 锁），每 1s 扫描：
  - `status=ready` 且依赖全部 `passed` 的 Step；
  - 租约过期的 `running` Step；
  - 超时的任务/步骤；
  - 重试队列。
- 按 `priority desc, created_at asc` 派发。
- 每个队列有并发上限；Worker 注册时声明队列与并发。

### 10.3 租约与心跳

```sql
UPDATE task_steps
SET status='running', lease_until=now()+interval '10 min', heartbeat_at=now()
WHERE id=:id AND status='ready';
```

- Worker 每 30s 更新 `heartbeat_at`；
- 超过 `lease_until` 未完成 → 回收为 `ready`，`attempt += 1`；
- `attempt > max_attempts` → `failed` + 告警。

### 10.4 错误分类

| 类型 | 例子 | 处理 |
|---|---|---|
| `Transient` | 网络超时、429、临时 5xx | 退避重试，最多 3 次 |
| `Resource` | OOM、磁盘满 | 降并发/换 Worker，重试 1 次 |
| `Validation` | 因子编译失败、Schema 不符 | 回到实现/Agent 修复，不自动重试 |
| `Fatal` | 数据缺失、权限、快照不存在 | 终止 + 通知 |
| `Cancelled` | 用户取消 | 清理，不重试 |

### 10.5 死信队列

- 超过重试次数 → `q.dead`；
- H5 展示失败原因、重试按钮；
- 管理员可手动重放（记录审计）。

### 10.6 幂等与缓存

- Step 执行前计算 `cache_key`；命中则复制产物、直接 `passed`；
- 写产物使用内容寻址，重复写无副作用；
- DB 更新使用条件更新（`WHERE status='running'`）。

---

## 11. 可观测性

### 11.1 日志

结构化 JSON：

```json
{
  "ts": "2026-10-17T10:00:00Z",
  "level": "info",
  "service": "worker-validation",
  "task_id": "tsk_...",
  "step_id": "stp_...",
  "trace_id": "...",
  "event": "gate.completed",
  "gate_id": "G1",
  "duration_ms": 1200
}
```

### 11.2 指标（Prometheus）

| 指标 | 类型 | 说明 |
|---|---|---|
| `tasks_total{status}` | counter | 任务数 |
| `task_duration_seconds` | histogram | 任务耗时 |
| `step_duration_seconds{step_type}` | histogram | 步骤耗时 |
| `queue_depth{queue}` | gauge | 队列深度 |
| `worker_busy{queue}` | gauge | 忙碌 Worker |
| `llm_tokens_total{model}` | counter | Token 消耗 |
| `llm_cost_usd_total` | counter | 成本 |
| `factor_cache_hit_ratio` | gauge | 缓存命中率 |
| `gate_failures_total{gate}` | counter | 门槛失败数 |
| `holdout_unlocks_total` | counter | OOS 解锁次数 |
| `http_request_duration_seconds` | histogram | API 延迟 |

### 11.3 链路

- 每个请求/Step 生成 `trace_id`；
- OpenTelemetry 导出到 Jaeger/Tempo（可选）；
- Agent 工具调用作为 span。

---

## 12. 示例流程

### 12.1 创建并跟踪任务

```text
POST /tasks
  → 201 {task_id}
GET /tasks/{task_id}/events  (SSE)
  ← snapshot
  ← step.started (scout)
  ← agent.tool_call (source.search)
  ← step.completed (scout)
  ← ...
  ← gate.result (G2 failed)
  ← task.completed (rejected)
GET /validation-runs/{run_id}/report
```

### 12.2 人工审批

```text
GET /tasks/{id}/events
  ← human.required {gate_id: G5}
POST /gates/{gate_id}/decision {decision: approve}
  → 200
  ← step.started (g6_strategy)
```

### 12.3 OOS 解锁

```text
GET /holdouts
POST /holdouts/{id}/unlock-requests
  → 202 {request_id}
POST /holdout-unlock-requests/{request_id}/approve
  → 200 {token, expires_at}
  ← step.started (g7_holdout)
  ← gate.result (G7 passed/failed)
  ← task.completed
GET /reports/{report_id}/export?format=pdf
```

---

## 13. 安全与限制

| 项 | 策略 |
|---|---|
| CORS | 仅允许配置的前端域名 |
| 请求体大小 | 默认 10 MB；上传另限 |
| 文件上传 | 类型/大小/病毒扫描；只允许 PDF/CSV/TXT/MD |
| 限流 | 每 token 60 req/min；SSE 并发 5 |
| 下载 | 签名 URL，短有效期（5 min） |
| SQL 注入 | ORM + 参数化 |
| SSRF | 来源抓取经专用网关，禁止私网 |
| 敏感信息 | 日志脱敏；密钥不入库/不入报告 |
| OpenAPI | 生产环境需鉴权或关闭 `/docs` |
| 审计 | 写操作、审批、解锁全记录 |

---

## 14. API 版本与兼容

- 路径版本 `/api/v1`；
- 新增字段向后兼容；删除/重命名升 `/api/v2`；
- 事件增加新 `event` 类型视为兼容；修改字段语义需升版本并在 `snapshot` 中声明；
- 前端从 OpenAPI 生成类型，CI 检查 breaking changes（如 `oasdiff`）。
