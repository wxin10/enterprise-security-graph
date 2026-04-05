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
- 当前不再继续保持“验收模式 / 无待办业务批”的结论，而是切换到新的整改批状态
- 当前系统真实状态为：后端已开放图谱、告警、封禁、监控接口；前端业务数据接口已有部分真实联调，但登录与路由权限仍以本地会话和本地角色逻辑为主
- 本轮进入“系统一致性整改批 1：登录页与主布局口径收口”，只允许修改 4 个强相关文件：`CODEX_NEXT.md`、`CODEX_PROGRESS.md`、`frontend/src/views/LoginView.vue`、`frontend/src/layouts/AppLayout.vue`
- 本轮目标不是新增功能，而是先把登录页、主布局和当前系统真实实现状态统一起来

---

# 1. 当前批次（最重要）

> 下面内容每次只保留“当前真正要做的一批”。

## 当前批次标题
系统一致性整改批 1：登录页与主布局口径收口

## 当前批次目标
- 先收口系统口径，不新增功能，不扩展更多页面
- 将登录页中的“模拟 / 演示 / 不接后端权限接口”等表述改为正式且真实的工程表达
- 将主布局顶部“前后端联调正常”这类过满表述改为符合当前实现状态的说明
- 保持当前可运行逻辑、菜单结构、角色显示、退出逻辑不变
- 将进度文件从验收模式切换到新的整改批状态，为后续真实整改批次留出入口

## 当前批次允许修改的文件
- `CODEX_NEXT.md`
- `CODEX_PROGRESS.md`
- `frontend/src/views/LoginView.vue`
- `frontend/src/layouts/AppLayout.vue`

## 当前批次禁止修改的文件
- 除本批允许修改的 4 个文件外，其余业务文件默认禁止修改
- 尤其不要回改：
  - `backend/app.py`
  - `backend/app/api/`
  - `backend/app/services/`
  - `frontend/src/router/index.js`
  - `frontend/src/api/http.js`
  - `frontend/src/styles/global.css`
  - `frontend/src/utils/auth.js`
  - `frontend/src/utils/mock-storage.js`
  - `frontend/src/views/AuditLogView.vue`
  - `frontend/src/views/UserManageView.vue`
  - `frontend/src/views/RuleManageView.vue`
  - `frontend/src/views/DashboardView.vue`
  - `frontend/src/views/MyRecordsView.vue`
  - `frontend/src/views/RequestActionView.vue`
  - `frontend/src/views/ForbiddenView.vue`
  - `frontend/src/views/ProfileView.vue`
  - `AGENTS.md`

## 当前批次进入条件
- 已读 `CODEX_PROGRESS.md`
- 已读 `CODEX_NEXT.md`
- 已检查 `git status --short`
- 已检查 `frontend/src/views/LoginView.vue`
- 已检查 `frontend/src/layouts/AppLayout.vue`
- 已检查 `frontend/src/router/index.js`
- 已检查 `frontend/src/api/http.js`
- 已检查 `frontend/src/utils/auth.js`
- 已检查 `backend/app.py`
- 已检查 `backend/app/api/` 与 `backend/app/services/`
- 已确认后端当前没有真实登录 / 用户 / 权限接口
- 已确认前端业务数据接口为部分真实联调，但登录与路由权限仍以本地会话逻辑为主
- 已确认登录页、主布局和路由守卫的系统口径不一致，因此需要先做文案与进度状态收口

## 当前批次验收标准
- `CODEX_PROGRESS.md` 与 `CODEX_NEXT.md` 已从“验收模式 / 无待办业务批”切换为新的整改批状态
- `frontend/src/views/LoginView.vue` 已去掉“模拟 / 演示 / 不接后端权限接口”等表述，文案改为正式且真实
- `frontend/src/layouts/AppLayout.vue` 顶部状态文案已改为符合当前工程实现状态的说法
- 本批不改 `router`、`auth`、`http`、backend 或任何业务页面本体
- 本批完成后，再根据真实现状决定是否需要开启下一轮一致性整改批

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
- 已从“无待办业务批”切换为“系统一致性整改批 1”
- 本轮仅处理登录页、主布局与进度文件口径收口
- 本轮完成后，再判断是否需要进入下一轮一致性整改，而不是直接恢复验收模式

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
