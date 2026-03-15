// 文件路径：frontend/src/router/index.js
// 作用说明：
// 1. 统一管理前端页面路由。
// 2. 将登录页与系统业务布局页分开，便于后续接入鉴权逻辑。
// 3. 当前阶段提供登录页、仪表盘页、告警管理页和封禁管理页。

import { createRouter, createWebHistory } from "vue-router";

import AppLayout from "@/layouts/AppLayout.vue";
import AlertsView from "@/views/AlertsView.vue";
import BansView from "@/views/BansView.vue";
import DashboardView from "@/views/DashboardView.vue";
import LoginView from "@/views/LoginView.vue";

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
            title: "仪表盘"
          }
        },
        {
          path: "alerts",
          name: "alerts",
          component: AlertsView,
          meta: {
            title: "告警管理"
          }
        },
        {
          path: "bans",
          name: "bans",
          component: BansView,
          meta: {
            title: "封禁管理"
          }
        }
      ]
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: "/login"
    }
  ]
});

// 当前阶段先不做真实登录鉴权。
// 这里只负责根据路由元信息更新浏览器标题，方便演示与调试。
router.afterEach((to) => {
  const pageTitle = to.meta?.title ? `${to.meta.title} - 企业安全图谱平台` : "企业安全图谱平台";
  document.title = pageTitle;
});

export default router;
