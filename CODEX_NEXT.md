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

- [x] 正常模式：本批最多 2 个文件
- [ ] 降级模式：本批只处理 1 个文件
- [ ] 恢复模式：先核对上一批是否真实落地
- [ ] 验收模式：本轮只核验，不改代码

## 当前建议模式
- 上一轮无中断，本轮可继续按正常模式推进
- 由于普通用户页面本体已落地但入口未打通，下一批优先处理路由与布局接入

---

# 1. 当前批次（最重要）

> 下面内容每次只保留“当前真正要做的一批”。

## 当前批次标题
批次 6：接入普通用户页面路由与菜单

## 当前批次目标
- 在 `frontend/src/router/index.js` 中补上无权限页、个人中心页、我的处理记录页和处置申请页的路由入口
- 在 `frontend/src/layouts/AppLayout.vue` 中补上普通用户可见菜单，让已创建页面能从控制台进入
- 严格保持现有登录逻辑、权限工具和页面本体不变，只做入口接入

## 当前批次允许修改的文件
- `frontend/src/router/index.js`
- `frontend/src/layouts/AppLayout.vue`

## 当前批次禁止修改的文件
- 除本批允许文件外，其余业务文件默认禁止修改
- 尤其不要回改：
  - `frontend/src/views/MyRecordsView.vue`
  - `frontend/src/views/RequestActionView.vue`
  - `frontend/src/views/ForbiddenView.vue`
  - `frontend/src/views/ProfileView.vue`
  - `frontend/src/views/LoginView.vue`
  - `frontend/src/utils/auth.js`
  - `frontend/src/utils/mock-storage.js`
  - `AGENTS.md`

## 当前批次进入条件
- 已读 `CODEX_PROGRESS.md`
- 已读 `CODEX_NEXT.md`
- 已检查 `git status --short`
- 已明确本批只处理路由和布局两个文件
- 已确认当前页面文件本体已存在，下一步目标是打通访问入口

## 当前批次验收标准
- `frontend/src/router/index.js` 已接入对应路由
- `frontend/src/layouts/AppLayout.vue` 已补上普通用户菜单入口
- 普通用户不会被误做成访客，仍能访问核心业务页面
- `git status --short` 可见对应变更
- 已更新 `CODEX_PROGRESS.md`
- 已重写本文件并切换到后续业务批

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
13. 审计日志页

## 阶段 E：白色主题统一
14. 统一 `global.css`
15. 局部页面白色主题微调

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
- 状态：当前下一批

### 批次 7
- `frontend/src/views/UserManageView.vue`
- `frontend/src/views/RuleManageView.vue`

### 批次 8
- `frontend/src/views/AuditLogView.vue`

### 批次 9
- `frontend/src/styles/global.css`

---

# 4. 当前批次生成规则（给 Codex 的硬规则）

1. 如果上一轮发生断流：
   - 先进入恢复模式
   - 核验上一轮声称改动的文件是否真实落地
   - 只从未完成的最小一批继续

2. 如果上一轮已完整落地：
   - 直接进入当前最小下一批
   - 不跨批改动页面本体、全局样式和管理员页面

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
