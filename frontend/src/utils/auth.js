// 文件路径：frontend/src/utils/auth.js
// 作用说明：
// 1. 统一维护控制台会话信息、角色、菜单和按钮权限配置。
// 2. 为登录页、路由守卫、主布局菜单和页面权限控制提供公共方法。
// 3. 统一收口当前用户读取、会话恢复与会话清理逻辑。

export const STORAGE_USER_KEY = "console_current_user";
export const LEGACY_STORAGE_USER_KEY = "mock_login_user";
export const STORAGE_SESSION_TOKEN_KEY = "console_session_token";
export const BACKEND_BASE_URL = "http://127.0.0.1:5000";

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
  { path: "/console/alerts", label: "告警中心", icon: "Bell", roles: [ROLE_ADMIN, ROLE_USER] },
  { path: "/console/monitor", label: "日志监控中心", icon: "Monitor", roles: [ROLE_ADMIN, ROLE_USER] },
  { path: "/console/disposals", label: "处置申请", icon: "DocumentAdd", roles: [ROLE_USER] },
  { path: "/console/my-records", label: "我的处理记录", icon: "Tickets", roles: [ROLE_USER] },
  { path: "/console/bans", label: "封禁审批", icon: "Lock", roles: [ROLE_ADMIN] },
  { path: "/console/users", label: "用户管理", icon: "UserFilled", roles: [ROLE_ADMIN] },
  { path: "/console/rules", label: "规则管理", icon: "SetUp", roles: [ROLE_ADMIN] },
  { path: "/console/audit", label: "审计日志", icon: "Document", roles: [ROLE_ADMIN] },
  { path: "/console/profile", label: "个人中心", icon: "User", roles: [ROLE_ADMIN, ROLE_USER] }
];

const LEGACY_ACCOUNT_USER_TEMPLATES = {
  admin: {
    user_id: "ADMIN-001",
    username: "admin",
    display_name: "平台管理员",
    department: "安全运营中心",
    title: "高权限运维负责人",
    role: ROLE_ADMIN
  },
  analyst: {
    user_id: "OPS-001",
    username: "analyst",
    display_name: "值班分析员",
    department: "安全运营中心",
    title: "一线运维 / 安全分析员",
    role: ROLE_USER
  },
  user: {
    user_id: "OPS-002",
    username: "user",
    display_name: "一线运维人员",
    department: "安全运营中心",
    title: "一线运维 / 安全分析员",
    role: ROLE_USER
  }
};

let restoreSessionPromise = null;

function normalizeAccountName(username) {
  return String(username || "").trim().toLowerCase();
}

function normalizeStoredUser(user) {
  if (!user || typeof user !== "object") {
    return null;
  }

  return {
    ...user,
    role: normalizeRole(user.role)
  };
}

function removeUserStorage() {
  sessionStorage.removeItem(STORAGE_USER_KEY);
  sessionStorage.removeItem(LEGACY_STORAGE_USER_KEY);
}

function resolveStoredUser(rawValue) {
  if (!rawValue) {
    return null;
  }

  try {
    return normalizeStoredUser(JSON.parse(rawValue));
  } catch (error) {
    return buildLegacyUserByAccount(rawValue);
  }
}

function buildLegacyUserByAccount(username) {
  // 这个兼容分支只用于读取旧版本浏览器里已经存在的本地会话数据。
  // 当前正式登录链路已经切到后端鉴权接口，不再依赖这里生成用户。
  const normalizedAccount = normalizeAccountName(username);
  const template = LEGACY_ACCOUNT_USER_TEMPLATES[normalizedAccount];
  if (!template) {
    return null;
  }

  return {
    ...template,
    login_at: new Date().toISOString()
  };
}

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

export function getMenuItemByPath(path) {
  return MENU_ITEMS.find((item) => item.path === path) || null;
}

export function buildMenuRouteMeta(path, extraMeta = {}) {
  const menuItem = getMenuItemByPath(path);

  if (!menuItem) {
    return {
      ...extraMeta
    };
  }

  return {
    title: menuItem.label,
    roles: menuItem.roles,
    ...extraMeta
  };
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

export function saveSessionToken(sessionToken) {
  const normalizedToken = String(sessionToken || "").trim();

  if (!normalizedToken) {
    sessionStorage.removeItem(STORAGE_SESSION_TOKEN_KEY);
    return "";
  }

  sessionStorage.setItem(STORAGE_SESSION_TOKEN_KEY, normalizedToken);
  return normalizedToken;
}

export function getSessionToken() {
  return String(sessionStorage.getItem(STORAGE_SESSION_TOKEN_KEY) || "").trim();
}

export function saveCurrentUser(user) {
  const normalizedUser = normalizeStoredUser(user);

  if (!normalizedUser) {
    removeUserStorage();
    return null;
  }

  sessionStorage.setItem(STORAGE_USER_KEY, JSON.stringify(normalizedUser));
  sessionStorage.removeItem(LEGACY_STORAGE_USER_KEY);
  return normalizedUser;
}

export function saveCurrentSession(sessionPayload = {}) {
  // 登录成功后统一在这里保存后端返回的会话令牌和当前用户。
  // 这样 router、layout 和各页面继续只读 auth.js，就不需要感知后端接口细节。
  const resolvedToken = saveSessionToken(sessionPayload.session_token || sessionPayload.token || "");
  const resolvedUser = saveCurrentUser(sessionPayload.user);

  if (!resolvedToken || !resolvedUser) {
    return null;
  }

  return resolvedUser;
}

export function clearCurrentSession() {
  removeUserStorage();
  sessionStorage.removeItem(STORAGE_SESSION_TOKEN_KEY);
}

export function getCurrentUser() {
  const currentRawValue = sessionStorage.getItem(STORAGE_USER_KEY);
  const currentUser = resolveStoredUser(currentRawValue);

  if (currentUser) {
    if (currentRawValue !== JSON.stringify(currentUser)) {
      saveCurrentUser(currentUser);
    }
    return currentUser;
  }

  if (currentRawValue) {
    sessionStorage.removeItem(STORAGE_USER_KEY);
  }

  const legacyRawValue = sessionStorage.getItem(LEGACY_STORAGE_USER_KEY);
  const legacyUser = resolveStoredUser(legacyRawValue);

  if (legacyUser) {
    saveCurrentUser(legacyUser);
    sessionStorage.removeItem(LEGACY_STORAGE_USER_KEY);
    return legacyUser;
  }

  if (legacyRawValue) {
    sessionStorage.removeItem(LEGACY_STORAGE_USER_KEY);
  }

  return null;
}

export function clearCurrentUser() {
  clearCurrentSession();
}

export async function restoreCurrentUserFromSession() {
  const currentUser = getCurrentUser();
  if (currentUser) {
    return currentUser;
  }

  if (restoreSessionPromise) {
    return restoreSessionPromise;
  }

  const sessionToken = getSessionToken();
  if (!sessionToken) {
    clearCurrentSession();
    return null;
  }

  restoreSessionPromise = (async () => {
    try {
      const response = await fetch(`${BACKEND_BASE_URL}/api/auth/me`, {
        method: "GET",
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${sessionToken}`
        }
      });

      const responseData = await response.json().catch(() => null);

      if (!response.ok || typeof responseData?.code !== "number" || responseData.code !== 0 || !responseData?.data?.user) {
        if (response.status === 401) {
          clearCurrentSession();
        }
        return null;
      }

      saveCurrentSession(responseData.data);
      return getCurrentUser();
    } catch (error) {
      return null;
    } finally {
      restoreSessionPromise = null;
    }
  })();

  return restoreSessionPromise;
}

export async function ensureCurrentUser() {
  const currentUser = getCurrentUser();
  if (currentUser) {
    return currentUser;
  }

  const sessionToken = getSessionToken();
  if (!sessionToken) {
    clearCurrentSession();
    return null;
  }

  const restoredUser = await restoreCurrentUserFromSession();
  if (!restoredUser && !getSessionToken()) {
    clearCurrentSession();
  }

  return restoredUser;
}
