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
- 当前进入“完整系统收口批 1-14：MonitorCenterView 正式化文案和样式收口”收尾阶段
- 本轮只同步进度文件、复核语法并准备提交推送，不再改动业务代码
- 本轮允许修改 2 个文件：`CODEX_NEXT.md`、`CODEX_PROGRESS.md`
- 本轮完成后重置为等待用户指定新的最小批次

---

# 1. 当前批次（最重要）

> 下面内容每次只保留“当前真正要做的一批”。

## 当前批次标题
完整系统收口批 1-14：MonitorCenterView 正式化文案和样式收口

## 当前批次目标
- 同步 `frontend/src/views/MonitorCenterView.vue` 正式化文案与样式收口结果到进度文件
- 再次复核 `frontend/src/views/MonitorCenterView.vue` 的语法状态
- 完成本轮版本提交与推送准备
- 本轮不再改动任何业务代码

## 当前批次允许修改的文件
- `CODEX_NEXT.md`
- `CODEX_PROGRESS.md`

## 当前批次禁止修改的文件
- 除本批允许修改的 2 个文件外，其余业务文件默认禁止修改
- 尤其不要回改：
  - `frontend/src/views/MonitorCenterView.vue`
  - `frontend/src/views/`
  - `frontend/src/router/`
  - `frontend/src/layouts/`
  - `frontend/src/utils/`
  - `backend/`
  - `AGENTS.md`

## 当前批次进入条件
- 已读 `CODEX_PROGRESS.md`
- 已读 `CODEX_NEXT.md`
- 已检查 `git status --short`
- 已确认当前分支为 `current-ui-sync`
- 已确认 `frontend/src/views/MonitorCenterView.vue` 已完成正式化文案与样式收口
- 已确认当前工作区仅包含本轮相关变更
- 已确认本轮不是恢复模式
- 已确认本轮只做文档同步、语法复核与提交推送准备

## 当前批次验收标准
- `CODEX_PROGRESS.md` 与 `CODEX_NEXT.md` 已同步记录“完整系统收口批 1-14：MonitorCenterView 正式化文案和样式收口”
- `frontend/src/views/MonitorCenterView.vue` 已再次通过 `@vue/compiler-sfc` 语法检查
- 当前分支保持为 `current-ui-sync`
- 本轮完成后进入“等待用户指定下一批任务”状态

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
- 当前处于“完整系统收口批 1-14：MonitorCenterView 正式化文案和样式收口”收尾阶段
- 本轮只同步进度文件、复核语法并准备提交推送
- 本轮完成后重置为等待用户指定新的最小批次

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

---

## 2026-04-06 收尾更新

### 当前状态
- 当前批次已完成 `frontend/src/views/DashboardView.vue` 的真实图表接入。
- 当前收尾仅同步进度文件并准备提交推送。
- 当前分支：`current-ui-sync`。

### 下一批建议
- 等待用户指定新的最小批次。
- 如继续前端增量开发，继续遵守单批最小范围原则。

### 收尾批次说明
- 本轮业务落地文件：`frontend/src/views/DashboardView.vue`
- 本轮收尾文件：`CODEX_PROGRESS.md`、`CODEX_NEXT.md`
- 本轮校验：`frontend/src/views/DashboardView.vue` 已再次通过 `@vue/compiler-sfc` 语法检查

---

## 2026-04-06 收尾更新
### 当前状态
- `frontend/src/views/ProfileView.vue` 与 `frontend/src/views/UserManageView.vue` 已完成正式化文案和样式收口。
- 当前收尾仅同步进度文件并准备提交推送。
- 当前分支：`current-ui-sync`。

### 下一批建议
- 等待用户指定新的最小批次。
- 如继续前端增量开发，继续遵守单批最小范围原则。

### 收尾批次说明
- 本轮业务落地文件：`frontend/src/views/ProfileView.vue`、`frontend/src/views/UserManageView.vue`
- 本轮收尾文件：`CODEX_PROGRESS.md`、`CODEX_NEXT.md`
- 本轮校验：`frontend/src/views/ProfileView.vue`、`frontend/src/views/UserManageView.vue` 已再次通过 `@vue/compiler-sfc` 语法检查

## 2026-04-06 AppLayout 与 router 状态文案收口
### 当前状态
- `frontend/src/layouts/AppLayout.vue` 已将顶部状态提示收口为正式业务表达。
- `frontend/src/router/index.js` 已清理顶部状态提示相关的实现层 meta 文案。
- 当前分支仍为 `current-ui-sync`。
### 下一批建议
- 等待用户指定新的最小批次。
- 如继续前端收口，继续遵守单批最小范围原则。
### 收尾批次说明
- 本轮业务落地文件：`frontend/src/layouts/AppLayout.vue`、`frontend/src/router/index.js`
- 本轮收尾文件：`CODEX_PROGRESS.md`、`CODEX_NEXT.md`
- 本轮校验：`frontend/src/layouts/AppLayout.vue` 与 `frontend/src/router/index.js` 将执行语法检查。
### 校验结果补录
- `frontend/src/layouts/AppLayout.vue` 已通过 `@vue/compiler-sfc` 语法检查。
- `frontend/src/router/index.js` 已通过 `node --check` 语法检查。

## 2026-04-06 Dashboard 残留清理收尾
### 当前状态
- `frontend/src/views/DashboardView.vue` 已清理失效的旧 `summaryCards` 注释块。
- `frontend/src/views/DashboardView.vue` 已删除与 `ChartPlaceholder` 相关的无效残留样式。
- 当前分支仍为 `current-ui-sync`。
### 下一批建议
- 等待用户指定新的最小批次。
- 如继续前端收口，继续遵守单文件最小范围原则。
### 收尾批次说明
- 本轮业务落地文件：`frontend/src/views/DashboardView.vue`
- 本轮收尾文件：`CODEX_PROGRESS.md`、`CODEX_NEXT.md`
- 本轮校验：`frontend/src/views/DashboardView.vue` 已执行语法检查。

## 2026-04-06 ForbiddenView 正式化收尾
### 当前状态
- `frontend/src/views/ForbiddenView.vue` 已完成正式系统口径文案收口。
- `frontend/src/views/ForbiddenView.vue` 已完成本地样式收口并统一为白色企业后台风格。
- 当前分支仍为 `current-ui-sync`。
### 下一批建议
- 等待用户指定新的最小批次。
- 如继续前端收口，继续遵守单文件最小范围原则。
### 收尾批次说明
- 本轮业务落地文件：`frontend/src/views/ForbiddenView.vue`
- 本轮收尾文件：`CODEX_PROGRESS.md`、`CODEX_NEXT.md`
- 本轮校验：`frontend/src/views/ForbiddenView.vue` 已执行语法检查。

## 2026-04-06 AlertsView 正式化收尾
### 当前状态
- `frontend/src/views/AlertsView.vue` 已完成正式系统口径文案收口。
- `frontend/src/views/AlertsView.vue` 已完成本地样式收口并统一复用现有主题变量。
- 当前收尾仅同步进度文件并准备提交推送。
- 当前分支：`current-ui-sync`。

### 下一批建议
- 等待用户指定新的最小批次。
- 如继续前端增量开发，继续遵守单批最小范围原则。

### 收尾批次说明
- 本轮业务落地文件：`frontend/src/views/AlertsView.vue`
- 本轮收尾文件：`CODEX_PROGRESS.md`、`CODEX_NEXT.md`
- 本轮校验：`frontend/src/views/AlertsView.vue` 已再次通过 `@vue/compiler-sfc` 语法检查。

## 2026-04-06 AlertsView 二次收尾
### 当前状态
- `frontend/src/views/AlertsView.vue` 本轮未再修改业务代码。
- 已再次完成 `frontend/src/views/AlertsView.vue` 语法检查。
- 当前收尾仅同步进度文件并准备提交推送。
- 当前分支：`current-ui-sync`。

### 下一批建议
- 等待用户指定新的最小批次。
- 如继续前端增量开发，继续遵守单批最小范围原则。

### 收尾批次说明
- 本轮业务落地文件：无
- 本轮收尾文件：`CODEX_PROGRESS.md`、`CODEX_NEXT.md`
- 本轮校验：`frontend/src/views/AlertsView.vue` 已再次通过 `@vue/compiler-sfc` 语法检查。

## 2026-04-06 ProfileView 文本修复收尾
### 当前状态
- `frontend/src/views/ProfileView.vue` 已修复顶部副标题中的异常文本显示。
- `frontend/src/views/ProfileView.vue` 已修复未登录头像与 `userInitial` 的兜底字符显示。
- 当前收尾仅同步进度文件并准备提交推送。
- 当前分支：`current-ui-sync`。

### 下一批建议
- 等待用户指定新的最小批次。
- 如继续前端增量开发，继续遵守单批最小范围原则。

### 收尾批次说明
- 本轮业务落地文件：`frontend/src/views/ProfileView.vue`
- 本轮收尾文件：`CODEX_PROGRESS.md`、`CODEX_NEXT.md`
- 本轮校验：`frontend/src/views/ProfileView.vue` 已通过 `@vue/compiler-sfc` 语法检查。

## 2026-04-06 ProfileView 文本修复终收尾
### 当前状态
- `frontend/src/views/ProfileView.vue` 顶部副标题已收口为指定的正式中文句子。
- `frontend/src/views/ProfileView.vue` 未登录头像显示继续保持为正常中文字符“登”。
- 当前收尾仅同步进度文件并准备提交推送。
- 当前分支：`current-ui-sync`。

### 下一批建议
- 等待用户指定新的最小批次。
- 如继续前端增量开发，继续遵守单批最小范围原则。

### 收尾批次说明
- 本轮业务落地文件：`frontend/src/views/ProfileView.vue`
- 本轮收尾文件：`CODEX_PROGRESS.md`、`CODEX_NEXT.md`
- 本轮校验：`frontend/src/views/ProfileView.vue` 已通过 `@vue/compiler-sfc` 语法检查。

## 2026-04-06 UserManageView 文本修复收尾
### 当前状态
- `frontend/src/views/UserManageView.vue` 已修复页面中的异常文本显示。
- `frontend/src/views/UserManageView.vue` 已恢复副标题、筛选说明、列表提示、角色边界说明、空状态与操作提示的正常中文表达。
- 当前收尾仅同步进度文件并准备提交推送。
- 当前分支：`current-ui-sync`。

### 下一批建议
- 等待用户指定新的最小批次。
- 如继续前端增量开发，继续遵守单批最小范围原则。

### 收尾批次说明
- 本轮业务落地文件：`frontend/src/views/UserManageView.vue`
- 本轮收尾文件：`CODEX_PROGRESS.md`、`CODEX_NEXT.md`
- 本轮校验：`frontend/src/views/UserManageView.vue` 已通过 `@vue/compiler-sfc` 语法检查。

## 2026-04-06 UserManageView 去演示化收尾
### 当前状态
- `frontend/src/views/UserManageView.vue` 已将待审批事项区块说明文案改为正式系统表达。
- `frontend/src/views/UserManageView.vue` 用户可见文案中已移除“演示”字样。
- 当前收尾仅同步进度文件并准备提交推送。
- 当前分支：`current-ui-sync`。

### 下一批建议
- 等待用户指定新的最小批次。
- 如继续前端增量开发，继续遵守单批最小范围原则。

### 收尾批次说明
- 本轮业务落地文件：`frontend/src/views/UserManageView.vue`
- 本轮收尾文件：`CODEX_PROGRESS.md`、`CODEX_NEXT.md`
- 本轮校验：`frontend/src/views/UserManageView.vue` 已通过 `@vue/compiler-sfc` 语法检查。

## 2026-04-06 RuleManageView 正式化收尾
### 当前状态
- `frontend/src/views/RuleManageView.vue` 已完成正式系统口径文案收口。
- `frontend/src/views/RuleManageView.vue` 已完成本地样式收口并统一为白色企业后台风格。
- 当前收尾仅同步进度文件并准备提交推送。
- 当前分支：`current-ui-sync`。

### 下一批建议
- 等待用户指定新的最小批次。
- 如继续前端增量开发，继续遵守单批最小范围原则。

### 收尾批次说明
- 本轮业务落地文件：`frontend/src/views/RuleManageView.vue`
- 本轮收尾文件：`CODEX_PROGRESS.md`、`CODEX_NEXT.md`
- 本轮校验：`frontend/src/views/RuleManageView.vue` 已通过 `@vue/compiler-sfc` 语法检查。
## 2026-04-06 AuditLogView 正式化收尾
### 当前状态
- `frontend/src/views/AuditLogView.vue` 已完成正式系统文案收口。
- `frontend/src/views/AuditLogView.vue` 已完成本地样式收口并统一为白色企业后台风格。
- 当前收尾仅同步进度文件并准备提交推送。
- 当前分支仍为 `current-ui-sync`。

### 下一批建议
- 等待用户指定新的最小批次。
- 如继续前端收口，继续遵守单文件最小范围原则。

### 收尾批次说明
- 本轮业务落地文件：`frontend/src/views/AuditLogView.vue`
- 本轮收尾文件：`CODEX_PROGRESS.md`、`CODEX_NEXT.md`
- 本轮校验：`frontend/src/views/AuditLogView.vue` 已通过 `@vue/compiler-sfc` 语法检查。
## 2026-04-06 MyRecordsView 正式化收尾
### 当前状态
- `frontend/src/views/MyRecordsView.vue` 已完成正式系统文案收口。
- `frontend/src/views/MyRecordsView.vue` 已完成本地样式收口并统一为白色企业后台风格。
- 当前收尾仅同步进度文件并准备提交推送。
- 当前分支仍为 `current-ui-sync`。

### 下一批建议
- 等待用户指定新的最小批次。
- 如继续前端收口，继续遵守单文件最小范围原则。

### 收尾批次说明
- 本轮业务落地文件：`frontend/src/views/MyRecordsView.vue`
- 本轮收尾文件：`CODEX_PROGRESS.md`、`CODEX_NEXT.md`
- 本轮校验：`frontend/src/views/MyRecordsView.vue` 已通过 `@vue/compiler-sfc` 语法检查。
## 2026-04-06 RequestActionView 正式化收尾
### 当前状态
- `frontend/src/views/RequestActionView.vue` 已完成正式系统文案收口。
- `frontend/src/views/RequestActionView.vue` 已完成本地样式收口并统一为白色企业后台风格。
- 当前收尾仅同步进度文件并准备提交推送。
- 当前分支仍为 `current-ui-sync`。

### 下一批建议
- 等待用户指定新的最小批次。
- 如继续前端收口，继续遵守单文件最小范围原则。

### 收尾批次说明
- 本轮业务落地文件：`frontend/src/views/RequestActionView.vue`
- 本轮收尾文件：`CODEX_PROGRESS.md`、`CODEX_NEXT.md`
- 本轮校验：`frontend/src/views/RequestActionView.vue` 已通过 `@vue/compiler-sfc` 语法检查。

## 2026-04-06 BansView 正式化收尾
### 当前状态
- `frontend/src/views/BansView.vue` 已完成正式系统口径文案收口。
- `frontend/src/views/BansView.vue` 已完成本地样式收口并统一为白色企业后台风格。
- 当前收尾仅同步进度文件并准备提交推送。
- 当前分支仍为 `current-ui-sync`。

### 下一批建议
- 等待用户指定新的最小批次。
- 如继续前端收口，继续遵守单文件最小范围原则。

### 收尾批次说明
- 本轮业务落地文件：`frontend/src/views/BansView.vue`
- 本轮收尾文件：`CODEX_PROGRESS.md`、`CODEX_NEXT.md`
- 本轮校验：`frontend/src/views/BansView.vue` 已通过 `@vue/compiler-sfc` 语法检查。

## 2026-04-06 MonitorCenterView 正式化收尾
### 当前状态
- `frontend/src/views/MonitorCenterView.vue` 已完成正式系统口径文案收口。
- `frontend/src/views/MonitorCenterView.vue` 已完成本地样式收口并统一为白色企业后台风格。
- 当前收尾仅同步进度文件、复核语法并准备提交推送。
- 当前分支仍为 `current-ui-sync`。

### 下一批建议
- 等待用户指定新的最小批次。
- 如继续前端收口，继续遵守单文件最小范围原则。

### 收尾批次说明
- 本轮业务落地文件：`frontend/src/views/MonitorCenterView.vue`
- 本轮收尾文件：`CODEX_PROGRESS.md`、`CODEX_NEXT.md`
- 本轮校验：`frontend/src/views/MonitorCenterView.vue` 已再次通过 `@vue/compiler-sfc` 语法检查。

## 2026-04-06 审批流页面闭环与会话持久化收尾
### 当前状态
- `frontend/src/views/BansView.vue` 已接入真实待审批申请列表、通过/驳回动作与审批备注录入。
- `frontend/src/views/AuditLogView.vue`、`frontend/src/views/MyRecordsView.vue`、`frontend/src/views/RequestActionView.vue` 已联动展示审批结果与审批备注。
- `backend/app/services/auth_service.py` 已改为基于 `backend/app/data/session_state.json` 的持久化会话实现。
- 当前分支仍为 `current-ui-sync`。

### 下一批建议
- 等待用户指定新的最小批次。
- 如继续系统收口，优先补管理员处置结果与封禁执行记录的进一步联动展示。

### 收尾批次说明
- 本轮业务落地文件：
  - `backend/app/services/governance_service.py`
  - `backend/app/services/auth_service.py`
  - `backend/app/api/auth_api.py`
  - `backend/app/data/governance_state.json`
  - `backend/app/data/session_state.json`
  - `frontend/src/views/BansView.vue`
  - `frontend/src/views/AuditLogView.vue`
  - `frontend/src/views/MyRecordsView.vue`
  - `frontend/src/views/RequestActionView.vue`
- 本轮收尾文件：`CODEX_PROGRESS.md`、`CODEX_NEXT.md`
- 本轮校验：
  - `npm.cmd run build` 已执行成功。
  - `python -m py_compile backend/app/services/governance_service.py backend/app/services/auth_service.py backend/app/api/auth_api.py` 已执行成功。
  - 审批流与会话持久化联调均已完成。
## 2026-04-06 下一批建议
### 当前状态
- 首页已接入审批概览卡片、待审批申请区块和最近审批记录区块，管理员可在工作台直接处理审批。
- 封禁申请审批通过后已写入联动封禁结果，`BansView.vue`、`MyRecordsView.vue`、`RequestActionView.vue`、`AuditLogView.vue` 已同步展示来源说明、审批备注和联动状态。
- 基础后端回归测试已落地到 `tests/`，本轮已完成 `py_compile`、`pytest`、前端构建和脚本联调验证。
- 当前分支仍为 `current-ui-sync`，工作区继续保持连续收口状态。

### 下一批建议
- 如继续做运营收口，优先补首页更多管理统计卡片与封禁执行统计的联动展示。
- 如继续做质量保障，优先补前端联调测试或端到端测试，覆盖首页审批动作和封禁联动展示。
- 如继续做产品化闭环，可评估把联动封禁详情进一步沉淀到封禁接口返回，减少前端组合字段的耦合。
