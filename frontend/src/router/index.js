// 文件路径：frontend/src/router/index.js
// 作用说明：
// 1. 统一管理前端页面路由。
// 2. 保持登录页与业务控制台布局分离，便于后续继续扩展权限系统。
// 3. 当前阶段的访问控制由前端会话守卫生效，并通过路由 meta 明确区分“后端接口数据页”和“本地状态页”。
import { createRouter, createWebHistory } from "vue-router";
import { ElMessage } from "element-plus";

import AppLayout from "@/layouts/AppLayout.vue";
import AlertsView from "@/views/AlertsView.vue";
import AuditLogView from "@/views/AuditLogView.vue";
import BansView from "@/views/BansView.vue";
import DashboardView from "@/views/DashboardView.vue";
import ForbiddenView from "@/views/ForbiddenView.vue";
import LoginView from "@/views/LoginView.vue";
import MonitorCenterView from "@/views/MonitorCenterView.vue";
import MyRecordsView from "@/views/MyRecordsView.vue";
import ProfileView from "@/views/ProfileView.vue";
import RequestActionView from "@/views/RequestActionView.vue";
import RuleManageView from "@/views/RuleManageView.vue";
import UserManageView from "@/views/UserManageView.vue";
import { canAccessRoles, ensureCurrentUser, getCurrentUser, getRoleHomePath, ROLE_ADMIN, ROLE_USER } from "@/utils/auth";

const CONSOLE_ROLES = [ROLE_ADMIN, ROLE_USER];
const AUTH_MODE_FRONTEND_SESSION = "frontend-session-guard";
const DATA_SOURCE_BACKEND = "backend-api";
const DATA_SOURCE_LOCAL = "local-state";

const ROUTE_STATUS_NOTES = {
  [DATA_SOURCE_BACKEND]: "当前页面数据已接入后端接口，访问范围按前端会话守卫生效",
  [DATA_SOURCE_LOCAL]: "当前页面数据仍以本地状态为主，访问范围按前端会话守卫生效"
};

function getRouteStatusNote(dataSource) {
  return ROUTE_STATUS_NOTES[dataSource] || "当前页面访问范围按前端会话守卫生效，模块数据按页面实现分别接入";
}

function findNearestRouteRecord(to, predicate) {
  return [...to.matched].reverse().find(predicate);
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      redirect: "/login"
    },
    {
      path: "/login",
      name: "login",
      component: LoginView,
      meta: {
        title: "登录"
      }
    },
    {
      path: "/console",
      component: AppLayout,
      meta: {
        requiresAuth: true,
        roles: CONSOLE_ROLES,
        authMode: AUTH_MODE_FRONTEND_SESSION,
        dataSource: DATA_SOURCE_LOCAL,
        statusNote: "当前控制台访问范围按前端会话守卫生效，页面数据按模块分别接入"
      },
      children: [
        {
          path: "",
          redirect: "/console/dashboard"
        },
        {
          path: "dashboard",
          name: "dashboard",
          component: DashboardView,
          meta: {
            title: "工作台",
            roles: CONSOLE_ROLES,
            dataSource: DATA_SOURCE_BACKEND,
            statusNote: getRouteStatusNote(DATA_SOURCE_BACKEND)
          }
        },
        {
          path: "alerts",
          name: "alerts",
          component: AlertsView,
          meta: {
            title: "告警中心",
            roles: CONSOLE_ROLES,
            dataSource: DATA_SOURCE_BACKEND,
            statusNote: getRouteStatusNote(DATA_SOURCE_BACKEND)
          }
        },
        {
          path: "bans",
          name: "bans",
          component: BansView,
          meta: {
            title: "封禁审批",
            roles: [ROLE_ADMIN],
            dataSource: DATA_SOURCE_BACKEND,
            statusNote: getRouteStatusNote(DATA_SOURCE_BACKEND)
          }
        },
        {
          path: "users",
          name: "users",
          component: UserManageView,
          meta: {
            title: "用户管理",
            roles: [ROLE_ADMIN],
            dataSource: DATA_SOURCE_LOCAL,
            statusNote: getRouteStatusNote(DATA_SOURCE_LOCAL)
          }
        },
        {
          path: "rules",
          name: "rules",
          component: RuleManageView,
          meta: {
            title: "规则管理",
            roles: [ROLE_ADMIN],
            dataSource: DATA_SOURCE_LOCAL,
            statusNote: getRouteStatusNote(DATA_SOURCE_LOCAL)
          }
        },
        {
          path: "audit",
          name: "audit",
          component: AuditLogView,
          meta: {
            title: "审计日志",
            roles: [ROLE_ADMIN],
            dataSource: DATA_SOURCE_LOCAL,
            statusNote: getRouteStatusNote(DATA_SOURCE_LOCAL)
          }
        },
        {
          path: "monitor",
          name: "monitor",
          component: MonitorCenterView,
          meta: {
            title: "日志监控中心",
            roles: CONSOLE_ROLES,
            dataSource: DATA_SOURCE_BACKEND,
            statusNote: getRouteStatusNote(DATA_SOURCE_BACKEND)
          }
        },
        {
          path: "forbidden",
          name: "forbidden",
          component: ForbiddenView,
          meta: {
            title: "无权限访问",
            roles: CONSOLE_ROLES,
            dataSource: DATA_SOURCE_LOCAL,
            statusNote: getRouteStatusNote(DATA_SOURCE_LOCAL)
          }
        },
        {
          path: "profile",
          name: "profile",
          component: ProfileView,
          meta: {
            title: "个人中心",
            roles: CONSOLE_ROLES,
            dataSource: DATA_SOURCE_LOCAL,
            statusNote: getRouteStatusNote(DATA_SOURCE_LOCAL)
          }
        },
        {
          path: "my-records",
          name: "my-records",
          component: MyRecordsView,
          meta: {
            title: "我的处理记录",
            roles: CONSOLE_ROLES,
            dataSource: DATA_SOURCE_LOCAL,
            statusNote: getRouteStatusNote(DATA_SOURCE_LOCAL)
          }
        },
        {
          path: "disposals",
          name: "disposals",
          component: RequestActionView,
          meta: {
            title: "处置申请",
            roles: CONSOLE_ROLES,
            dataSource: DATA_SOURCE_LOCAL,
            statusNote: getRouteStatusNote(DATA_SOURCE_LOCAL)
          }
        }
      ]
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: () => {
        const currentUser = getCurrentUser();
        return currentUser ? getRoleHomePath(currentUser.role) : "/login";
      }
    }
  ]
});

router.beforeEach(async (to) => {
  let currentUser = getCurrentUser();
  if (!currentUser) {
    currentUser = await ensureCurrentUser();
  }

  const currentRoleHomePath = currentUser ? getRoleHomePath(currentUser.role) : "/login";
  const requiresAuth = to.matched.some((record) => record.meta?.requiresAuth);
  const authModeRecord = findNearestRouteRecord(to, (record) => typeof record.meta?.authMode === "string");
  const authMode = authModeRecord?.meta?.authMode || AUTH_MODE_FRONTEND_SESSION;
  const accessMetaRecord = findNearestRouteRecord(to, (record) => Array.isArray(record.meta?.roles));
  const accessRoles = accessMetaRecord?.meta?.roles || [];

  if (to.path === "/login") {
    if (currentUser) {
      return currentRoleHomePath;
    }

    return true;
  }

  if (requiresAuth && authMode === AUTH_MODE_FRONTEND_SESSION && !currentUser) {
    return "/login";
  }

  if (accessRoles.length > 0 && !canAccessRoles(currentUser, accessRoles)) {
    ElMessage.warning("当前账号无权访问该页面，已为你跳转到无权限说明页");
    return {
      path: "/console/forbidden",
      query: {
        from: to.fullPath
      }
    };
  }

  return true;
});

// 保留原有标题更新逻辑，同时让角色接入后依然便于调试和答辩演示。
router.afterEach((to) => {
  const pageTitle = to.meta?.title ? `${to.meta.title} - 企业安全图谱平台` : "企业安全图谱平台";
  document.title = pageTitle;
});

export default router;
