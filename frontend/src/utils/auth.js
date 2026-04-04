// 文件路径：frontend/src/utils/auth.js
// 作用说明：
// 1. 统一维护前端模拟登录用户、角色、菜单和按钮权限配置。
// 2. 为登录页、路由守卫、主布局菜单和后续页面权限控制提供公共方法。
// 3. 当前阶段不依赖后端权限接口，优先保证毕业设计演示流程完整。

export const STORAGE_USER_KEY = "mock_login_user";

export const ROLE_ADMIN = "admin";
export const ROLE_USER = "user";

export const ROLE_LABEL_MAP = {
  [ROLE_ADMIN]: "管理员",
  [ROLE_USER]: "普通用户"
};

export const ROLE_HOME_MAP = {
  [ROLE_ADMIN]: "/console/dashboard",
  [ROLE_USER]: "/console/dashboard"
};

export const LOGIN_ROLE_OPTIONS = [
  {
    value: ROLE_ADMIN,
    label: ROLE_LABEL_MAP[ROLE_ADMIN],
    description: "高权限运维负责人，可执行审批、规则管理和最终封禁。"
  },
  {
    value: ROLE_USER,
    label: ROLE_LABEL_MAP[ROLE_USER],
    description: "一线运维 / 安全分析员，可研判告警、分析图谱并发起申请。"
  }
];

export const PERMISSION_KEYS = {
  ALERT_MARK: "alert:mark",
  DISPOSAL_APPLY: "disposal:apply",
  DISPOSAL_VIEW_SELF: "disposal:view-self",
  BAN_EXECUTE: "ban:execute",
  BAN_VERIFY: "ban:verify",
  USER_MANAGE: "user:manage",
  RULE_MANAGE: "rule:manage",
  AUDIT_VIEW: "audit:view",
  CONFIG_MANAGE: "config:manage"
};

export const ROLE_PERMISSION_MAP = {
  [ROLE_ADMIN]: [
    PERMISSION_KEYS.ALERT_MARK,
    PERMISSION_KEYS.DISPOSAL_APPLY,
    PERMISSION_KEYS.DISPOSAL_VIEW_SELF,
    PERMISSION_KEYS.BAN_EXECUTE,
    PERMISSION_KEYS.BAN_VERIFY,
    PERMISSION_KEYS.USER_MANAGE,
    PERMISSION_KEYS.RULE_MANAGE,
    PERMISSION_KEYS.AUDIT_VIEW,
    PERMISSION_KEYS.CONFIG_MANAGE
  ],
  [ROLE_USER]: [
    PERMISSION_KEYS.ALERT_MARK,
    PERMISSION_KEYS.DISPOSAL_APPLY,
    PERMISSION_KEYS.DISPOSAL_VIEW_SELF
  ]
};

export const MENU_ITEMS = [
  { path: "/console/dashboard", label: "工作台", icon: "DataLine", roles: [ROLE_ADMIN, ROLE_USER] },
  { path: "/console/detections", label: "检测结果", icon: "Monitor", roles: [ROLE_ADMIN, ROLE_USER] },
  { path: "/console/alerts", label: "告警中心", icon: "Bell", roles: [ROLE_ADMIN, ROLE_USER] },
  { path: "/console/graph", label: "图谱分析", icon: "Share", roles: [ROLE_ADMIN, ROLE_USER] },
  { path: "/console/disposals", label: "处置申请", icon: "DocumentAdd", roles: [ROLE_USER] },
  { path: "/console/my-records", label: "我的处理记录", icon: "Tickets", roles: [ROLE_USER] },
  { path: "/console/bans", label: "封禁审批", icon: "Lock", roles: [ROLE_ADMIN] },
  { path: "/console/users", label: "用户管理", icon: "UserFilled", roles: [ROLE_ADMIN] },
  { path: "/console/rules", label: "规则管理", icon: "SetUp", roles: [ROLE_ADMIN] },
  { path: "/console/audit", label: "审计日志", icon: "Document", roles: [ROLE_ADMIN] },
  { path: "/console/profile", label: "个人中心", icon: "User", roles: [ROLE_ADMIN, ROLE_USER] }
];

const USER_TEMPLATES = {
  [ROLE_ADMIN]: {
    user_id: "ADMIN-001",
    username: "admin",
    display_name: "平台管理员",
    department: "安全运营中心",
    title: "高权限运维负责人",
    role: ROLE_ADMIN
  },
  [ROLE_USER]: {
    user_id: "OPS-001",
    username: "analyst",
    display_name: "值班分析员",
    department: "安全运营中心",
    title: "一线运维 / 安全分析员",
    role: ROLE_USER
  }
};

export function normalizeRole(role) {
  return role === ROLE_ADMIN ? ROLE_ADMIN : ROLE_USER;
}

export function getRoleLabel(role) {
  return ROLE_LABEL_MAP[normalizeRole(role)];
}

export function getRoleHomePath(role) {
  return ROLE_HOME_MAP[normalizeRole(role)];
}

export function getMenuItemsByRole(role) {
  const normalizedRole = normalizeRole(role);
  return MENU_ITEMS.filter((item) => item.roles.includes(normalizedRole));
}

export function getPermissionList(role) {
  return ROLE_PERMISSION_MAP[normalizeRole(role)] || [];
}

export function hasPermission(user, permissionKey) {
  return Boolean(user) && getPermissionList(user.role).includes(permissionKey);
}

export function canAccessRoles(user, roles = []) {
  if (!roles || roles.length === 0) {
    return true;
  }

  return Boolean(user) && roles.includes(normalizeRole(user.role));
}

export function buildMockUser(formModel = {}) {
  const resolvedRole = normalizeRole(formModel.role);
  const template = USER_TEMPLATES[resolvedRole];

  return {
    ...template,
    username: String(formModel.username || template.username).trim() || template.username,
    display_name: String(formModel.display_name || template.display_name).trim() || template.display_name,
    role: resolvedRole,
    login_at: new Date().toISOString()
  };
}

export function saveCurrentUser(user) {
  sessionStorage.setItem(STORAGE_USER_KEY, JSON.stringify(user));
}

export function clearCurrentUser() {
  sessionStorage.removeItem(STORAGE_USER_KEY);
}

export function getCurrentUser() {
  const rawValue = sessionStorage.getItem(STORAGE_USER_KEY);
  if (!rawValue) {
    return null;
  }

  try {
    const parsedValue = JSON.parse(rawValue);
    return parsedValue ? { ...parsedValue, role: normalizeRole(parsedValue.role) } : null;
  } catch (error) {
    // 兼容旧版本仅保存账号字符串的情况，避免已有演示数据失效。
    const fallbackRole = String(rawValue).toLowerCase().includes("admin") ? ROLE_ADMIN : ROLE_USER;
    const fallbackUser = buildMockUser({ username: rawValue, role: fallbackRole });
    saveCurrentUser(fallbackUser);
    return fallbackUser;
  }
}
