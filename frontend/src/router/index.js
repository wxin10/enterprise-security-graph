// 文件路径：frontend/src/router/index.js
// 作用说明：
// 1. 统一管理前端页面路由。
// 2. 保持登录页与业务控制台布局分离，便于后续继续扩展权限系统。
// 3. 当前阶段在现有页面基础上接入前端模拟角色守卫，区分管理员和普通用户访问范围。
import { createRouter, createWebHistory } from "vue-router";
import { ElMessage } from "element-plus";

import AppLayout from "@/layouts/AppLayout.vue";
import AlertsView from "@/views/AlertsView.vue";
import BansView from "@/views/BansView.vue";
import DashboardView from "@/views/DashboardView.vue";
import LoginView from "@/views/LoginView.vue";
import MonitorCenterView from "@/views/MonitorCenterView.vue";
import { canAccessRoles, getCurrentUser, getRoleHomePath, ROLE_ADMIN, ROLE_USER } from "@/utils/auth";

const CONSOLE_ROLES = [ROLE_ADMIN, ROLE_USER];

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
        roles: CONSOLE_ROLES
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
            roles: CONSOLE_ROLES
          }
        },
        {
          path: "alerts",
          name: "alerts",
          component: AlertsView,
          meta: {
            title: "告警中心",
            roles: CONSOLE_ROLES
          }
        },
        {
          path: "bans",
          name: "bans",
          component: BansView,
          meta: {
            title: "封禁审批",
            roles: [ROLE_ADMIN]
          }
        },
        {
          path: "monitor",
          name: "monitor",
          component: MonitorCenterView,
          meta: {
            title: "日志监控中心",
            roles: CONSOLE_ROLES
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

// 当前阶段采用前端模拟登录态。
// 在不改动现有页面结构的前提下，为控制台路由补充基础鉴权和角色拦截。
router.beforeEach((to) => {
  const currentUser = getCurrentUser();
  const currentRoleHomePath = currentUser ? getRoleHomePath(currentUser.role) : "/login";
  const requiresAuth = to.matched.some((record) => record.meta?.requiresAuth);
  const accessMeta = [...to.matched].reverse().find((record) => Array.isArray(record.meta?.roles));
  const accessRoles = accessMeta?.meta?.roles || [];

  if (to.path === "/login") {
    if (currentUser) {
      return currentRoleHomePath;
    }

    return true;
  }

  if (requiresAuth && !currentUser) {
    return "/login";
  }

  if (accessRoles.length > 0 && !canAccessRoles(currentUser, accessRoles)) {
    ElMessage.warning("当前账号无权访问该页面，已为你返回工作台");
    return currentRoleHomePath;
  }

  return true;
});

// 保留原有标题更新逻辑，同时让角色接入后依然便于调试和答辩演示。
router.afterEach((to) => {
  const pageTitle = to.meta?.title ? `${to.meta.title} - 企业安全图谱平台` : "企业安全图谱平台";
  document.title = pageTitle;
});

export default router;
