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
- 当前继续处于系统一致性整改阶段，但整改重点已从“登录角色由账号决定”切换到“登录提示与本地会话边界说明收口”
- 当前系统真实状态为：登录角色已改为由账号决定，但登录、菜单权限和路由守卫仍属于前端本地会话链路，页面表达还需要进一步收口
- 本轮进入“系统一致性整改批 4：登录提示与本地会话边界说明收口”，只允许修改 4 个强相关文件：`CODEX_NEXT.md`、`CODEX_PROGRESS.md`、`frontend/src/views/LoginView.vue`、`frontend/src/layouts/AppLayout.vue`
- 本轮目标不是新增功能，而是把登录提示、主布局状态文案和当前主结论统一到“本地会话 + 部分后端接口联调”的真实状态

---

# 1. 当前批次（最重要）

> 下面内容每次只保留“当前真正要做的一批”。

## 当前批次标题
系统一致性整改批 4：登录提示与本地会话边界说明收口

## 当前批次目标
- 保留当前“账号决定角色”的登录逻辑，不新增功能、不改动后端
- 将登录页提示收口为正式、克制、专业的控制台会话表达，不再沿用模糊口径
- 将主布局顶部状态文案收口为“本地会话登录 + 分页面数据接入”的真实描述
- 在进度文件中明确：登录角色已改为账号决定，但当前登录与权限控制仍属于前端本地会话链路
- 将进度文件同步切换到新的整改批状态，为后续继续细化本地会话边界说明留出入口

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
  - `frontend/src/api/http.js`
  - `frontend/src/router/index.js`
  - `frontend/src/utils/auth.js`
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
  - `AGENTS.md`

## 当前批次进入条件
- 已读 `CODEX_PROGRESS.md`
- 已读 `CODEX_NEXT.md`
- 已检查 `git status --short`
- 已确认当前分支为 `current-ui-sync`
- 已检查 `frontend/src/views/LoginView.vue`
- 已检查 `frontend/src/layouts/AppLayout.vue`
- 已检查 `frontend/src/utils/auth.js`
- 已检查 `frontend/src/router/index.js`
- 已确认登录角色已由账号决定，`auth.js` 继续负责本地会话用户生成与保存
- 已确认菜单权限与路由守卫仍由 `currentUser.role` 驱动，属于前端本地会话链路
- 已确认工作台、告警、封禁、日志监控等页面存在后端接口接入，但并非所有页面都已联通后端
- 已确认本轮只需改登录提示、主布局状态文案和进度文件，不需要触碰 backend、`auth.js`、`router` 或业务页面本体

## 当前批次验收标准
- `CODEX_PROGRESS.md` 与 `CODEX_NEXT.md` 已切换为“系统一致性整改批 4”状态
- `frontend/src/views/LoginView.vue` 已将登录提示改为符合当前控制台会话机制的正式表达
- `frontend/src/layouts/AppLayout.vue` 已将顶部状态文案改为符合“本地会话 + 分页面数据接入”真实状态的说明
- `CODEX_PROGRESS.md` 已明确“登录角色已改为账号决定”与“当前登录和权限控制仍属前端本地会话链路”
- 本批不改 backend、`auth.js`、`router`、`http.js` 或任何业务页面本体

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
- 已从“系统一致性整改批 3”切换为“系统一致性整改批 4”
- 本轮仅处理登录提示与本地会话边界说明，不新增页面、不改 backend、不扩展业务功能
- 本轮完成后，再判断是否需要进入下一轮一致性整改，而不是继续保留模糊或过满的系统表达

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
