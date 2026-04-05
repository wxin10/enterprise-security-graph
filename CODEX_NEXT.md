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
- 当前继续处于登录与鉴权链路整改阶段，但整改重点已从“前端本地会话边界说明收口”切换到“后端真实登录接口落地”
- 当前系统真实状态为：前端登录角色已由账号决定，但 backend 仍缺少真实登录 / 当前用户接口，因此前端登录、菜单权限与路由守卫仍依赖本地会话链路
- 本轮进入“后端真实登录最小闭环批 1：后端鉴权接口落地”，只允许修改 5 个强相关文件：`CODEX_NEXT.md`、`CODEX_PROGRESS.md`、`backend/app/services/auth_service.py`、`backend/app/api/auth_api.py`、`backend/app/api/routes.py`
- 本轮目标不是接前端，而是在 backend 内补出最小可用的真实登录接口闭环，为下一轮前端切换到后端登录提供稳定接口基础

---

# 1. 当前批次（最重要）

> 下面内容每次只保留“当前真正要做的一批”。

## 当前批次标题
后端真实登录最小闭环批 1：后端鉴权接口落地

## 当前批次目标
- 在 backend 内补出最小真实登录接口闭环，不改 frontend 页面与本地会话逻辑
- 新增 `POST /api/auth/login` 与 `GET /api/auth/me` 两个接口
- 账号口径沿用当前前端 `auth.js`：`admin` 对应管理员，`analyst` / `user` 对应普通用户
- 登录成功后返回兼容前端现有用户结构的 `user` 数据以及可供后续接入的 `session_token`
- 当前阶段允许采用后端内存态会话 / 轻量令牌实现，但必须复用现有统一响应格式与错误处理风格
- 将进度文件同步切换到新的整改批状态，为下一轮前端切换到后端真实登录留出入口

## 当前批次允许修改的文件
- `CODEX_NEXT.md`
- `CODEX_PROGRESS.md`
- `backend/app/services/auth_service.py`
- `backend/app/api/auth_api.py`
- `backend/app/api/routes.py`

## 当前批次禁止修改的文件
- 除本批允许修改的 5 个文件外，其余业务文件默认禁止修改
- 尤其不要回改：
  - `frontend/src/utils/auth.js`
  - `frontend/src/views/LoginView.vue`
  - `frontend/src/layouts/AppLayout.vue`
  - `frontend/src/router/index.js`
  - `frontend/src/api/http.js`
  - `frontend/src/styles/global.css`
  - `frontend/src/utils/mock-storage.js`
  - `frontend/src/views/AuditLogView.vue`
  - `frontend/src/views/UserManageView.vue`
  - `frontend/src/views/RuleManageView.vue`
  - `frontend/src/views/DashboardView.vue`
  - `frontend/src/views/MyRecordsView.vue`
  - `frontend/src/views/RequestActionView.vue`
  - `frontend/src/views/ForbiddenView.vue`
  - `frontend/src/views/ProfileView.vue`
  - `backend/app.py`
  - `backend/app/api/alert_api.py`
  - `backend/app/api/ban_api.py`
  - `backend/app/api/graph_api.py`
  - `backend/app/api/monitor_api.py`
  - `backend/app/services/ban_service.py`
  - `backend/app/services/graph_service.py`
  - `backend/app/services/monitor_service.py`
  - `AGENTS.md`

## 当前批次进入条件
- 已读 `CODEX_PROGRESS.md`
- 已读 `CODEX_NEXT.md`
- 已检查 `git status --short`
- 已确认当前分支为 `current-ui-sync`
- 已检查 `backend/app.py`
- 已检查 `backend/config.py`
- 已检查 `backend/app/api/routes.py`
- 已检查 `backend/app/api/__init__.py`
- 已检查 `backend/app/core/response.py`
- 已检查 `backend/app/core/errors.py`
- 已检查 `backend/app/services/`
- 已检查 `frontend/src/utils/auth.js`
- 已检查 `frontend/src/views/LoginView.vue`
- 已确认 backend 当前通过 `backend/app/api/routes.py` 统一注册蓝图，并由 `backend/app/__init__.py` 挂载到 `/api`
- 已确认 backend 当前统一响应格式为 `code + message + data + timestamp`
- 已确认 backend 目前没有可复用的用户 / 权限 / 会话服务，需新增最小鉴权服务文件
- 已确认前端当前账号口径为：`admin`、`analyst`、`user`
- 已确认本轮只需改 backend 鉴权服务、鉴权接口、路由注册和进度文件，不需要触碰 frontend、`backend/app.py` 或现有业务接口

## 当前批次验收标准
- `CODEX_PROGRESS.md` 与 `CODEX_NEXT.md` 已切换为“后端真实登录最小闭环批 1”状态
- `backend/app/services/auth_service.py` 已落地后端最小登录 / 会话查询服务
- `backend/app/api/auth_api.py` 已提供 `POST /api/auth/login` 与 `GET /api/auth/me`
- `backend/app/api/routes.py` 已完成鉴权蓝图注册，且不破坏现有图谱、告警、封禁、监控接口
- 登录接口返回的 `user` 字段已与前端现有结构兼容，并包含 `session_token`
- 本批不改 frontend、`backend/app.py`、Neo4j 相关业务接口或任何业务页面本体

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
- 已从“系统一致性整改批 4”切换为“后端真实登录最小闭环批 1”
- 本轮仅处理 backend 登录接口闭环，不接 frontend、不扩展图谱/告警/封禁/监控功能
- 本轮完成后，下一轮优先进入“前端真实登录最小闭环批 2：前端调用 backend /api/auth/login”

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
