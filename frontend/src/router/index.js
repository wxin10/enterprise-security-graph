// 文件路径：frontend/src/router/index.js
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
import {
  buildMenuRouteMeta,
  canAccessRoles,
  ensureCurrentUser,
  getCurrentUser,
  getRoleHomePath,
  ROLE_ADMIN,
  ROLE_USER
} from "@/utils/auth";

const CONSOLE_ROLES = [ROLE_ADMIN, ROLE_USER];
const AUTH_MODE_FRONTEND_SESSION = "frontend-session-guard";
const DATA_SOURCE_BACKEND = "backend-api";
const DATA_SOURCE_LOCAL = "local-state";

const ROUTE_STATUS_NOTES = {
  [DATA_SOURCE_BACKEND]: "当前页面支持业务数据查看与风险处置，请按页面指引完成相关操作。",
  [DATA_SOURCE_LOCAL]: "当前页面支持信息维护与流程处理，请按职责范围办理相关事项。"
};

function getRouteStatusNote(dataSource) {
  return ROUTE_STATUS_NOTES[dataSource] || "当前页面状态正常，请按业务流程处理相关事项。";
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
        statusNote: "当前控制台运行正常，请按职责范围查看业务信息与处理待办事项。"
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
          meta: buildMenuRouteMeta("/console/dashboard", {
            dataSource: DATA_SOURCE_BACKEND,
            statusNote: getRouteStatusNote(DATA_SOURCE_BACKEND)
          })
        },
        {
          path: "alerts",
          name: "alerts",
          component: AlertsView,
          meta: buildMenuRouteMeta("/console/alerts", {
            dataSource: DATA_SOURCE_BACKEND,
            statusNote: getRouteStatusNote(DATA_SOURCE_BACKEND)
          })
        },
        {
          path: "bans",
          name: "bans",
          component: BansView,
          meta: buildMenuRouteMeta("/console/bans", {
            dataSource: DATA_SOURCE_BACKEND,
            statusNote: getRouteStatusNote(DATA_SOURCE_BACKEND)
          })
        },
        {
          path: "users",
          name: "users",
          component: UserManageView,
          meta: buildMenuRouteMeta("/console/users", {
            dataSource: DATA_SOURCE_LOCAL,
            statusNote: getRouteStatusNote(DATA_SOURCE_LOCAL)
          })
        },
        {
          path: "rules",
          name: "rules",
          component: RuleManageView,
          meta: buildMenuRouteMeta("/console/rules", {
            dataSource: DATA_SOURCE_LOCAL,
            statusNote: getRouteStatusNote(DATA_SOURCE_LOCAL)
          })
        },
        {
          path: "audit",
          name: "audit",
          component: AuditLogView,
          meta: buildMenuRouteMeta("/console/audit", {
            dataSource: DATA_SOURCE_LOCAL,
            statusNote: getRouteStatusNote(DATA_SOURCE_LOCAL)
          })
        },
        {
          path: "monitor",
          name: "monitor",
          component: MonitorCenterView,
          meta: buildMenuRouteMeta("/console/monitor", {
            dataSource: DATA_SOURCE_BACKEND,
            statusNote: getRouteStatusNote(DATA_SOURCE_BACKEND)
          })
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
          meta: buildMenuRouteMeta("/console/profile", {
            dataSource: DATA_SOURCE_LOCAL,
            statusNote: getRouteStatusNote(DATA_SOURCE_LOCAL)
          })
        },
        {
          path: "my-records",
          name: "my-records",
          component: MyRecordsView,
          meta: buildMenuRouteMeta("/console/my-records", {
            dataSource: DATA_SOURCE_LOCAL,
            statusNote: getRouteStatusNote(DATA_SOURCE_LOCAL)
          })
        },
        {
          path: "disposals",
          name: "disposals",
          component: RequestActionView,
          meta: buildMenuRouteMeta("/console/disposals", {
            dataSource: DATA_SOURCE_LOCAL,
            statusNote: getRouteStatusNote(DATA_SOURCE_LOCAL)
          })
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

router.afterEach((to) => {
  const pageTitle = to.meta?.title ? `${to.meta.title} - 企业安全图谱平台` : "企业安全图谱平台";
  document.title = pageTitle;
});

export default router;
