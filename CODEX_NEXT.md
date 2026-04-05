# CODEX_NEXT

> 作用：
> 这是当前 `design` 仓库的“下一批行动板”。
> 每次开始工作前必须先读取，并且每完成一批后立刻回写。
>
> 规则：
> - 这里只写“当前最小下一批”和“后续队列”
> - 默认每批最多处理 2 个文件
> - 如果发生中断，先切到恢复模式，不直接继续编码

---

# 0. 当前执行模式

请选择并维护当前模式：

- [ ] 正常模式：本批最多 2 个文件
- [ ] 降级模式：本批只处理 1 个文件
- [ ] 恢复模式：先核对上一批是否真实落地
- [x] 验收模式：本轮只核验，不改代码

## 当前建议模式
- 本轮已完成“进度纠偏批”，不需要恢复模式，也不再继续追加新的业务编码批次
- 已按真实工作区状态重新核对 9 个重点文件，确认它们均已真实落地，且此前已经登记，不存在“已落地但未登记”的管理员相关文件
- 当前仍保持验收模式；`frontend` 的 `npm.cmd run build` 最近一次执行仍受 `esbuild spawn EPERM` 阻塞，`node --check` 与相关 Vue SFC 编译检查通过
- 下一轮继续保持验收模式；若环境允许，优先重新执行 `frontend` 构建级校验

---

# 1. 当前批次（最重要）

> 下面内容每次只保留“当前真正要做的一批”。

## 当前批次标题
无待办业务批（进度已纠偏，等待可执行构建环境）

## 当前批次目标
- 已按“进度纠偏批”重新核对 9 个重点文件：`frontend/src/views/AuditLogView.vue`、`frontend/src/views/RuleManageView.vue`、`frontend/src/views/UserManageView.vue`、`frontend/src/router/index.js`、`frontend/src/layouts/AppLayout.vue`、`frontend/src/styles/global.css`、`frontend/src/views/DashboardView.vue`、`frontend/src/components/ChartPlaceholder.vue`、`frontend/src/components/StatCard.vue`
- 上述 9 个文件均已真实落地；其中管理员页面本体、管理员路由入口、管理员菜单入口和白色主题相关改动都已经写入工作区
- 本轮明确结论：已落地但未登记的文件为无；仍需继续开发的文件为无；当前不生成新的业务开发批
- 后续默认只做整体验收、工作区状态核对与可执行的构建级校验；若后续真发现业务缺口，再据实生成新的最小业务批

## 当前批次允许修改的文件
- 无待办业务文件
- 若进入验收模式，仅允许根据核验结果回写 `CODEX_PROGRESS.md` 与 `CODEX_NEXT.md`

## 当前批次禁止修改的文件
- 除验收回写所需的进度文件外，其余业务文件默认禁止修改
- 尤其不要回改：
  - `frontend/src/router/index.js`
  - `frontend/src/styles/global.css`
  - `frontend/src/utils/auth.js`
  - `frontend/src/utils/mock-storage.js`
  - `frontend/src/layouts/AppLayout.vue`
  - `frontend/src/views/DashboardView.vue`
  - `frontend/src/views/AuditLogView.vue`
  - `frontend/src/views/UserManageView.vue`
  - `frontend/src/views/RuleManageView.vue`
  - `frontend/src/views/MyRecordsView.vue`
  - `frontend/src/views/RequestActionView.vue`
  - `frontend/src/views/ForbiddenView.vue`
  - `frontend/src/views/ProfileView.vue`
  - `frontend/src/views/LoginView.vue`
  - `AGENTS.md`

## 当前批次进入条件
- 已读 `CODEX_PROGRESS.md`
- 已读 `CODEX_NEXT.md`
- 已检查 `git status --short`
- 已完成 2026-04-05 09:32 的进度纠偏：指定 9 个重点文件均已核对为真实落地，且此前已经登记
- 已确认当前没有待继续编码的最小业务批，后续应先做验收而不是扩展范围
- 已完成多次验收尝试：最近一次构建级验收仍失败于 `esbuild spawn EPERM`，但 `node --check frontend/src/router/index.js` 与相关 Vue 文件 SFC 编译检查通过
- 已明确下一轮继续只核验整体状态，不预先改动路由、权限、页面本体或全局样式入口

## 当前批次验收标准
- 已在 `CODEX_PROGRESS.md` 中明确记录“进度纠偏批”结论，并写清“已落地但未登记”为无、“仍需继续开发”为无
- 本文件已标记“无待办业务批”，并继续保持验收模式
- 下一轮如执行验收，优先重试 `frontend` 构建级校验；若环境仍阻塞，只输出真实核验结论，不强行继续编码

---

# 2. 推荐执行顺序（长期队列）

## 阶段 A：基础设施
1. 核验或补全 `frontend/src/utils/auth.js`
2. 核验或补全 `frontend/src/utils/mock-storage.js`

## 阶段 B：登录与权限主链路
3. 接入 `frontend/src/views/LoginView.vue`
4. 接入 `frontend/src/router/index.js`
5. 接入 `frontend/src/layouts/AppLayout.vue`

## 阶段 C：普通用户页面
6. 补充无权限页
7. 补充个人中心页
8. 补充我的处理记录页
9. 补充处置申请页
10. 接入普通用户页面路由与菜单

## 阶段 D：管理员页面
11. 用户管理页
12. 规则管理页
13. 接入用户管理 / 规则管理入口
14. 审计日志页
15. 接入审计日志入口

## 阶段 E：白色主题统一
16. 统一 `global.css`
17. 局部页面白色主题微调

---

# 3. 当前推荐批次切分

### 批次 1
- `frontend/src/utils/auth.js`
- `frontend/src/utils/mock-storage.js`
- 状态：已完成

### 批次 2
- `frontend/src/views/LoginView.vue`
- 状态：已完成

### 批次 3
- `frontend/src/router/index.js`
- `frontend/src/layouts/AppLayout.vue`
- 状态：已完成

### 批次 4
- `frontend/src/views/ForbiddenView.vue`
- `frontend/src/views/ProfileView.vue`
- 状态：已完成

### 批次 5
- `frontend/src/views/MyRecordsView.vue`
- `frontend/src/views/RequestActionView.vue`
- 状态：已完成

### 批次 6
- `frontend/src/router/index.js`
- `frontend/src/layouts/AppLayout.vue`
- 状态：已完成

### 批次 7
- `frontend/src/views/UserManageView.vue`
- `frontend/src/views/RuleManageView.vue`
- 状态：已完成

### 批次 8
- `frontend/src/router/index.js`
- `frontend/src/layouts/AppLayout.vue`
- 状态：已完成

### 批次 9
- `frontend/src/views/AuditLogView.vue`
- 状态：已完成

### 批次 10
- `frontend/src/router/index.js`
- `frontend/src/layouts/AppLayout.vue`
- 状态：已完成

### 批次 11
- `frontend/src/styles/global.css`
- 状态：已完成

### 批次 12
- `frontend/src/layouts/AppLayout.vue`
- `frontend/src/views/DashboardView.vue`
- 状态：已完成

### 批次 13
- `frontend/src/components/StatCard.vue`
- `frontend/src/components/ChartPlaceholder.vue`
- 状态：已完成

### 当前业务批状态
- 无待办业务批
- 下一轮继续保持验收模式
- 若环境允许，优先重新执行 `frontend` 的 `npm.cmd run build`
- 若环境仍然阻塞，只回写真实验收结论，不强行恢复业务编码

---

# 4. 当前批次生成规则（给 Codex 的硬规则）

1. 如果上一轮发生断流：
   - 先进入恢复模式
   - 核验上一轮声称改动的文件是否真实落地
   - 只从未完成的最小一批继续

2. 如果上一轮已完整落地：
   - 若仍有待办业务批，直接进入当前最小下一批
   - 若已无待办业务批，切到验收模式，不继续追加新业务改动

3. 如果发现当前页面已创建但入口未打通：
   - 优先安排“路由 + 布局”小批次补入口
   - 不允许继续堆积更多页面本体而不解决访问链路

---

# 5. 当前批次输出模板

- 本批目标：
- 本批允许修改文件：
- 本批实际修改文件：
- 当前 `git status --short`：
- 文件 A 改动说明：
- 文件 B 改动说明：
- 是否完成：
- 是否建议进入下一批：
- 下一批建议文件：

---

# 6. 用户常用短口令（Codex 必须理解）

- “继续下一批”
  - 含义：先读进度文件，再按本文档当前批次继续

- “先恢复”
  - 含义：进入恢复模式，先核对上一批是否真实落地

- “先验收”
  - 含义：只输出完整状态与 git 结果，不继续改代码

- “单文件模式”
  - 含义：当前批次降级为只处理 1 个文件

- “双文件模式”
  - 含义：当前批次最多处理 2 个文件

- “按 AGENTS.md 执行”
  - 含义：完整加载仓库长期规则并开始工作

---

# 7. 用户手动备注区（Codex 禁止覆盖）

> 用户可以在这里手写“下一步想先做什么”，Codex 只能读取参考。

（用户手动备注）
