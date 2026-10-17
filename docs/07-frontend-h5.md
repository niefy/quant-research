# 07 · H5 前端设计

> 目标：在手机上随时查看“任务队列、阶段进度、Agent 过程、验证结论”，并完成轻量审批。  
> 上游：[后端 API](06-backend-api.md)　下游：[安全与可复现](08-security-reproducibility.md)

---

## 1. 定位与约束

### 1.1 用户任务

| 场景 | 用户想做什么 | 页面 |
|---|---|---|
| 通勤/外出 | 看任务有没有跑完、卡在哪 | 看板、任务详情 |
| 收到告警 | 看失败原因、决定重试/放弃 | 任务详情、通知 |
| 需要审批 | 快速看证据并批准/拒绝 | 审批卡片 |
| 复盘 | 看因子指标、图表、报告 | 因子详情、报告 |
| 运维 | 看队列是否堵塞、Worker 是否在线 | 系统页 |

### 1.2 约束

- **移动优先**：375px 起，单手操作，底部 Tab。
- **监控优先**：复杂编辑/参数配置不在 H5 完成，引导到桌面端/API。
- **弱网可用**：SSE 断线重连、增量拉取、骨架屏、缓存最近数据。
- **信息密度可控**：默认摘要，详情按需展开；日志虚拟滚动。
- **安全**：不把 OOS 原始数据、密钥、完整论文全文展示在 H5。

---

## 2. 信息架构

```text
底部 Tab
├── 看板 /                    今日概览、运行中任务、告警
├── 任务 /tasks               队列与历史、筛选
│    └── /tasks/:id           详情：阶段、进度、日志、审批、产物
├── 因子 /factors             因子库、状态、指标
│    ├── /factors/:id         因子详情：规格、IC、分层、稳健性、相关性
│    └── /reports/:id         验证报告
└── 我的 /me
     ├── /queue               队列与 Worker（系统）
     ├── /sources            来源管理
     ├── /settings           阈值/预算/通知
     └── /notifications      通知中心
```

> 也可把“系统”独立为第四个 Tab；首期建议并入“我的”，保持 4 个 Tab。

### 2.1 路由表

| 路由 | 页面 | 鉴权 | 说明 |
|---|---|---|---|
| `/` | Dashboard | ✓ | 默认页 |
| `/tasks` | TaskList | ✓ | 查询参数保留筛选 |
| `/tasks/:id` | TaskDetail | ✓ | 支持 `?tab=timeline|logs|report` |
| `/factors` | FactorList | ✓ | — |
| `/factors/:id` | FactorDetail | ✓ | 默认概览 |
| `/reports/:id` | ReportDetail | ✓ | 可导出 |
| `/queue` | SystemQueue | ✓ | 队列/Worker |
| `/sources` | Sources | approver | 来源启停 |
| `/settings` | Settings | approver | 阈值/预算 |
| `/notifications` | Notifications | ✓ | — |
| `/login` | Login | — | Token 登录 |

---

## 3. 页面规格

### 3.1 看板（Dashboard）

**目标**：3 秒内回答“现在有没有问题”。

**区块**

1. **顶部状态条**：运行中 / 排队 / 今日失败 / 待审批。
2. **预算卡**：今日 token、成本、试验数（进度条）。
3. **运行中任务**：最多 5 张卡片，显示标题、阶段、进度、耗时、预计剩余（若可估）。
4. **待处理**：待审批 Gate、失败任务、预算超限。
5. **最近完成**：最近 5 条，带结论徽章（通过/拒绝/隔离）。
6. **队列迷你图**：各队列深度（可选）。

**交互**

- 下拉刷新；
- 点击卡片进入详情；
- 待审批卡片直接打开审批抽屉；
- 空状态引导创建任务（跳桌面端/API）。

### 3.2 任务列表（TaskList）

**筛选**

- 状态：全部 / 运行中 / 排队 / 待审批 / 失败 / 完成；
- 市场：全部 / crypto_perp / cn_equity；
- 时间：今天 / 7 天 / 30 天；
- 搜索：标题。

**列表项**

```text
[状态徽章] 加密市场短期动量因子
G2 分层组合 · 42%  ███████░░░
18 trials · 12m · 2 个告警
```

- 状态徽章颜色 + 文字（不只靠颜色）；
- 进度条 + 当前步骤；
- 试验数、耗时、告警数；
- 左滑快捷操作（暂停/取消）可选。

**分页**

- 游标无限滚动；
- 下拉刷新；
- 保留滚动位置。

### 3.3 任务详情（TaskDetail）

**结构**

```text
┌─────────────────────────────┐
│ ← 任务标题            [操作] │
│ 状态徽章 · 市场 · Profile     │
│ 总进度 ███████░░░ 42%        │
│ 预算: 430k/2M tokens · $4.2  │
├─────────────────────────────┤
│ 阶段 Stepper                │
│ ✓ Scout → ✓ Extract → ...   │
│ → G2 分层组合 (running 60%) │
├─────────────────────────────┤
│ Tabs: 过程 | 日志 | 门槛 | 产物│
├─────────────────────────────┤
│ (内容区)                     │
└─────────────────────────────┘
```

**阶段 Stepper**

- 横向可滚动；
- 节点状态：完成/运行/失败/等待审批/跳过；
- 点击节点滚动到对应事件或打开 Gate 详情；
- 显示每阶段耗时。

**Tab：过程（Agent Timeline）**

- 时间线：Agent 消息、工具调用、工具结果、结构化输出摘要；
- 工具调用可展开参数摘要与结果；
- 不展示完整思维链；只展示可审计摘要；
- 实时追加，自动滚动到底部（用户上滑后暂停自动滚动）。

**Tab：日志**

- 等宽字体，级别着色；
- 虚拟列表，保留最近 2000 行；
- 支持按级别过滤、搜索、复制；
- 断线时显示“重连中”，恢复后从 `Last-Event-ID` 续传。

**Tab：门槛**

- Gate 卡片列表：G0–G7；
- 每张卡：状态、关键指标、阈值、失败原因、图表缩略、证据链接；
- `waiting_human` 时显示审批按钮；
- 审批抽屉：摘要、风险点、批注、批准/拒绝。

**Tab：产物**

- 报告 JSON/PDF、因子值、图表、日志包；
- 显示大小、哈希、生成时间；
- 点击获取签名下载链接（移动端可分享/复制链接）。

**操作**

- 暂停/恢复/取消（带确认）；
- 重试失败步骤（仅 `retryable`）；
- 审批；
- 分享报告链接。

### 3.4 因子详情（FactorDetail）

**顶部**

- 名称、版本、状态徽章；
- 市场/scope/频率；
- 一句话经济逻辑；
- 来源引用（可跳转文档详情）。

**指标卡（2×2 或横滑）**

- Rank IC / ICIR / IC 胜率 / 试验数；
- 多空 Sharpe / 最大回撤 / PBO / DSR p。

**Tabs**

| Tab | 内容 |
|---|---|
| 概览 | 指标卡 + 结论 + 失败门槛 + 经济逻辑 |
| IC | IC 时序、累计 IC、IC 衰减、子期稳定性 |
| 分层 | 分组收益柱状图、多空净值、换手 |
| 稳健性 | 参数高原热力图/折线、状态分组收益、置换 p、Bootstrap 分布 |
| 相关性 | 与风险因子/内部因子相关矩阵、正交化残差 IC |
| 报告 | 完整报告入口、Gate 清单、导出 |

**规格（FactorSpec）**

- 折叠展示 YAML/JSON；
- 表达式高亮；
- 参数网格表格；
- 复制/下载。

**图表要求**

- 所有图表标注样本区间、样本量、成本假设；
- 失败门槛用明显标记（图标 + 文字，不只颜色）；
- 移动端图表高度 180–240px，支持横向滑动查看长序列；
- 长序列默认降采样，点击放大查看原始点。

### 3.5 报告页（ReportDetail）

- 结论横幅：通过 / 有条件通过 / 拒绝 / 隔离；
- 失败门槛置顶；
- 关键指标表；
- Gate 清单（可展开证据）；
- 试验统计：N、N_eff、失败数；
- 环境/快照/代码哈希；
- 下载 PDF/JSON；
- 分享链接（只读）。

### 3.6 系统页（SystemQueue）

- 队列深度：agent/data/factor/validation/backtest/report；
- Worker 列表：队列、心跳、当前 Step、并发；
- 吞吐：近 1h/24h 完成任务数；
- 死信：失败 Step、错误码、重试按钮；
- 存储/缓存命中率（可选）。

### 3.7 来源页（Sources）

- 来源卡片：名称、类型、启停、限速、许可状态；
- 同步按钮 + 最近同步时间；
- 新增来源（表单或 YAML 上传，approver）；
- 合规提示：付费墙/ToS/全文存储。

### 3.8 设置页（Settings）

- 默认 ValidationProfile；
- 预算默认值；
- 通知开关（任务完成/失败/待审批）；
- 主题（浅色/深色/跟随系统）；
- 关于/版本。

---

## 4. 组件设计

| 组件 | 职责 | 关键 props |
|---|---|---|
| `AppShell` | 底部 Tab、安全区、全局 Toast | — |
| `StatusBadge` | 状态徽章（图标+文字+颜色） | status, size |
| `TaskCard` | 任务摘要卡 | task |
| `ProgressRing` / `ProgressBar` | 进度 | value, status |
| `StageStepper` | 阶段时间线 | steps, current |
| `GateCard` | 门槛结果 | gate, onDecision |
| `ApprovalSheet` | 审批抽屉 | gate, onSubmit |
| `AgentTimeline` | Agent 事件时间线 | events |
| `LogViewer` | 虚拟日志 | lines, levelFilter |
| `MetricCard` | 指标卡 | label, value, threshold, status |
| `ChartCard` | 图表容器（标题/说明/图例） | title, spec, note |
| `ArtifactList` | 产物列表 | artifacts |
| `EmptyState` | 空状态 | icon, title, action |
| `Skeleton` | 骨架屏 | variant |
| `PullToRefresh` | 下拉刷新 | onRefresh |
| `ConnectionBanner` | SSE 连接状态 | state |

**组件原则**

- 展示组件不直接发请求；数据由页面/Store 注入；
- 所有状态（loading/empty/error/partial）都有明确 UI；
- 触控目标 ≥ 44×44 px；
- 支持 `prefers-reduced-motion`。

---

## 5. 状态管理（Pinia）

```text
stores/
├── auth.ts          # token、用户、权限
├── tasks.ts         # 列表、筛选、游标、增量同步
├── taskDetail.ts    # 当前任务、步骤、事件缓冲、连接状态
├── factors.ts       # 因子列表、详情缓存
├── reports.ts       # 报告缓存
├── system.ts        # 队列/Worker
├── notifications.ts # 通知、未读数
└── ui.ts            # 主题、Toast、全局 loading
```

**规则**

- 列表与详情分开缓存，避免列表刷新覆盖详情；
- 事件按 `task_id` 分桶，限制缓冲大小（如 5000 条）；
- SSE 事件先入缓冲，批量 `requestAnimationFrame` 更新 UI；
- 离开详情页可保留最近 N 条事件，重进时用 `updated_since` + SSE 补齐；
- 所有 Store 提供 `reset()` 便于登出/切换环境。

---

## 6. SSE 客户端

### 6.1 认证方式

`EventSource` 不能自定义 `Authorization` 头。两种方案：

**方案 A（推荐）：fetch + ReadableStream**

- 用 `fetch` 发 GET，带 `Authorization`，手动解析 `text/event-stream`；
- 可设置 header、读取 `Last-Event-ID`；
- 需要自己实现重连与帧解析；
- 适合 Bearer token。

**方案 B：同源 Cookie + EventSource**

- Nginx 同源部署，登录后写 HttpOnly Cookie；
- 直接用 `EventSource`；
- 需要 CSRF 防护（SSE 只读，风险较低）。

首期建议 **A**，保持 Bearer token 一致性。

### 6.2 客户端状态机

```text
idle → connecting → open → reconnecting → closed
                      │
                      └→ error (4xx: 停止；5xx/网络: 重连)
```

- 重连退避：1s, 2s, 4s, 8s, 16s, 30s（上限）；
- 随机抖动 ±20%；
- `visibilitychange`：进入后台暂停/降频；回到前台先增量拉取再重连；
- 页面卸载时关闭连接；
- 4xx（401/403/404）不重连，提示登录/任务不存在。

### 6.3 事件处理

```ts
type TaskEvent = {
  seq: number;
  type: string;
  task_id: string;
  step_id?: string;
  ts: string;
  data: Record<string, unknown>;
};

function applyEvent(store, event) {
  switch (event.type) {
    case "step.progress": store.updateStep(event); break;
    case "agent.tool_call": store.appendTimeline(event); break;
    case "gate.result": store.updateGate(event); break;
    case "human.required": store.showApproval(event); break;
    case "task.completed": store.finish(event); break;
  }
}
```

- 去重：记录 `lastSeq`，忽略 `seq <= lastSeq`；
- 乱序：按 `seq` 插入/排序；
- 缺失：检测序号跳跃，触发一次 `timeline?after_seq=` 补齐；
- 未知事件：记录但不崩溃（向前兼容）。

### 6.4 弱网策略

- 日志只保留最近 2000 行；
- 时间线只保留最近 500 条；
- 图表按需加载，不随事件实时重绘（完成时刷新）；
- 图片懒加载；
- 接口失败显示缓存 + “数据可能过期”标记。

---

## 7. 图表规格

> 图表统一使用 ECharts；所有图表遵循“颜色 + 形状/文字”双重编码，避免只靠红绿。

| 图表 | 类型 | 关键信息 | 交互 |
|---|---|---|---|
| IC 时序 | 柱/线 + 零线 | 每期 Rank IC、滚动均值 | 缩放、tooltip |
| 累计 IC | 折线 | 累计预测能力 | 区间选择 |
| IC 衰减 | 折线 | horizon 1/2/5/10/20 | 标注半衰期 |
| 分组收益 | 柱状 | Q1..Q5 平均收益 | 显示多空差 |
| 多空净值 | 折线 + 回撤阴影 | 净值、回撤 | 区间缩放 |
| 参数高原 | 热力图/折线 | 参数 × 指标 | 点击查看参数 |
| 状态分组 | 分组柱状 | 牛/熊/震荡收益 | 显示样本数 |
| 置换分布 | 直方图 | 零分布 + 观测值 | 标注 p 值 |
| 相关性矩阵 | 热力图 | 因子间相关 | 点击查看散点 |
| Bootstrap 回撤 | 直方图/密度 | MDD 分布 + 阈值 | 标注 P95 |
| Gate 清单 | 列表/步骤条 | 通过/失败/待审批 | 展开证据 |

**图表说明必须包含**：样本区间、样本量、成本假设、阈值线。禁止只放一张“漂亮的净值曲线”。

---

## 8. 移动端体验

### 8.1 布局

- 安全区：`env(safe-area-inset-*)`；
- 底部 Tab 高度 56px + 安全区；
- 页面内容底部留白，避免被 Tab 遮挡；
- 抽屉/弹层从底部升起，支持手势关闭。

### 8.2 主题

- 浅色/深色/跟随系统；
- 深色模式图表背景透明，网格线降低对比；
- 状态色：成功/失败/警告/运行中，均配图标与文字；
- 对比度 ≥ WCAG AA。

### 8.3 交互

- 下拉刷新（看板/列表）；
- 上拉加载更多；
- 左滑操作可选（不作为唯一入口）；
- 长按复制日志/哈希；
- 审批必须二次确认，危险操作（取消任务、OOS 解锁）需输入理由。

### 8.4 通知

- 站内通知中心 + 未读角标；
- 可选 Web Push（PWA）：任务完成、失败、待审批；
- 移动端后台 SSE 会挂起，通知依赖服务端推送/轮询；
- 通知内容不含敏感数据，只含任务标题/状态/深链。

### 8.5 无障碍

- 所有图标按钮有 `aria-label`；
- 状态不只靠颜色；
- 支持字体缩放（不写死 px 行高）；
- 尊重 `prefers-reduced-motion`；
- 键盘/读屏基础支持（桌面浏览器访问 H5 时）。

---

## 9. 性能

| 项 | 目标/策略 |
|---|---|
| 首屏 | < 2s（4G，缓存命中） |
| 路由 | 懒加载 + 代码分割 |
| 列表 | 虚拟滚动/分页，避免一次渲染上千条 |
| 日志 | 虚拟列表，最大 2000 行 |
| 图表 | 按需加载 ECharts 模块，完成时刷新 |
| 图片 | WebP/懒加载/缩略图 |
| 缓存 | 列表/详情 SWR + 本地持久化（可选） |
| SSE | 批量更新，避免每条事件触发重渲染 |
| 包体 | 目标 < 300 KB gzip（不含图表库按需） |

---

## 10. 错误与空状态

| 场景 | UI |
|---|---|
| 无任务 | 插画 + “创建任务”引导（桌面端/API） |
| 无权限 | 提示角色 + 申请入口 |
| 任务不存在 | 404 页 + 返回列表 |
| SSE 断线 | 顶部横幅“重连中”，保留已有数据 |
| 接口失败 | 错误卡片 + 重试按钮 + request_id |
| 报告生成中 | 骨架屏 + “生成后通知” |
| 预算超限 | 警示条 + 审批/终止入口 |
| OOS 已消耗 | 明确提示“该族已使用，不能再次解锁” |

---

## 11. 测试

| 类型 | 工具 | 覆盖 |
|---|---|---|
| 单元 | Vitest | Store、事件归并、格式化 |
| 组件 | Vue Test Utils | 状态徽章、GateCard、审批 |
| E2E | Playwright（移动视口） | 登录→任务列表→详情→审批 |
| SSE | Mock Server | 断线重连、乱序、缺号、心跳 |
| 视觉 | 截图对比 | 关键页面浅/深色 |
| 可访问性 | axe | 对比度、标签、触控 |

**Mock 数据**：提供 `fixtures/tasks.json`、`fixtures/events.ndjson`，前端可脱离后端开发。

---

## 12. 前端目录结构

```text
webui/
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── router/index.ts
│   ├── api/
│   │   ├── client.ts          # fetch 封装、错误、重试
│   │   ├── sse.ts             # fetch SSE 客户端
│   │   └── types.ts           # OpenAPI 生成
│   ├── stores/
│   ├── views/
│   │   ├── Dashboard.vue
│   │   ├── TaskList.vue
│   │   ├── TaskDetail.vue
│   │   ├── FactorList.vue
│   │   ├── FactorDetail.vue
│   │   ├── ReportDetail.vue
│   │   ├── SystemQueue.vue
│   │   ├── Sources.vue
│   │   ├── Settings.vue
│   │   └── Login.vue
│   ├── components/
│   │   ├── common/
│   │   ├── task/
│   │   ├── factor/
│   │   ├── charts/
│   │   └── approval/
│   ├── composables/
│   │   ├── useSSE.ts
│   │   ├── useInfiniteList.ts
│   │   └── useVisibility.ts
│   ├── styles/
│   └── fixtures/
├── tests/
└── package.json
```

---

## 13. 与后端的契约检查

- 前端类型从 OpenAPI 生成，CI 检查 breaking changes；
- SSE 事件类型在前后端共享 Schema（JSON Schema 或 TypeScript 类型生成）；
- 新增事件类型必须前端可忽略（向前兼容）；
- 所有时间使用 ISO8601 UTC，前端按用户时区显示；
- 金额/比率统一格式：百分比保留 1–2 位，Sharpe 保留 2 位，哈希显示前 8 位。

---

## 14. 首期页面优先级

| 优先级 | 页面 | 理由 |
|---|---|---|
| P0 | 任务列表、任务详情、SSE、审批 | 核心监控闭环 |
| P0 | 登录、错误/空状态 | 可用性 |
| P1 | 看板、报告页 | 快速总览 |
| P1 | 因子详情（概览/IC/分层） | 结果解读 |
| P2 | 系统页、来源页、设置 | 运维 |
| P2 | 稳健性/相关性图表 | 深度复盘 |
| P3 | Web Push、离线缓存、主题定制 | 体验增强 |
