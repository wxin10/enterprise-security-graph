<template>
  <!--
    文件路径：frontend/src/layouts/AppLayout.vue
    作用说明：
    1. 提供系统主布局，采用左侧菜单 + 顶部栏 + 内容区结构。
    2. 承载仪表盘、告警管理、封禁管理与日志监控中心等业务页面。
    3. 在现有布局基础上接入角色菜单和用户信息展示。
  -->
  <div class="layout-page">
    <el-container class="layout-shell">
      <el-aside class="layout-aside" width="240px">
        <div class="brand-panel">
          <div class="brand-mark">
            <el-icon><Monitor /></el-icon>
          </div>
          <div class="brand-text">
            <div class="brand-title">企业安全图谱平台</div>
            <div class="brand-subtitle">Enterprise Security Console</div>
          </div>
        </div>

        <el-menu
          :default-active="activeMenu"
          class="side-menu"
          background-color="transparent"
          text-color="var(--text-secondary)"
          active-text-color="var(--brand-primary)"
          @select="handleMenuSelect"
        >
          <el-menu-item v-for="item in sideMenuItems" :key="item.path" :index="item.path">
            <el-icon>
              <component :is="item.icon" />
            </el-icon>
            <span>{{ item.label }}</span>
          </el-menu-item>
        </el-menu>

        <div class="aside-user-card">
          <div class="aside-user-card__label">当前登录</div>
          <div class="aside-user-card__name">{{ currentUser?.display_name || "未登录用户" }}</div>
          <div class="aside-user-card__meta">
            <span>{{ currentUser?.username || "-" }}</span>
            <span>{{ currentRoleLabel }}</span>
          </div>
        </div>
      </el-aside>

      <el-container>
        <el-header class="layout-header">
          <div class="header-left">
            <div class="header-title">{{ currentPageTitle }}</div>
            <div class="header-status">
              <span class="status-dot status-dot--success"></span>
              当前版本已接入核心业务接口，控制台登录与菜单权限按当前会话状态加载
            </div>
          </div>

          <div class="header-right">
            <div class="header-user">
              <div class="header-user__name">{{ currentUser?.display_name || "未登录用户" }}</div>
              <div class="header-user__role">{{ currentRoleLabel }}</div>
            </div>
            <div class="header-time">{{ currentTimeText }}</div>
            <el-button type="primary" plain @click="handleLogout">
              <el-icon><SwitchButton /></el-icon>
              退出
            </el-button>
          </div>
        </el-header>

        <el-main class="layout-main">
          <RouterView />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
// 文件路径：frontend/src/layouts/AppLayout.vue
// 作用说明：
// 1. 管理系统主布局、菜单跳转和顶部标题。
// 2. 根据当前登录角色筛选可见菜单，并在顶部和侧边栏展示用户信息。
// 3. 通过定时器更新时间，展示控制台当前在线状态。
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { Bell, DataLine, Document, DocumentAdd, Lock, Monitor, SetUp, Tickets, User, UserFilled } from "@element-plus/icons-vue";
import { RouterView, useRoute, useRouter } from "vue-router";
import { clearCurrentUser, getCurrentUser, getMenuItemsByRole, getRoleLabel } from "@/utils/auth";

const router = useRouter();
const route = useRoute();

const currentTimeText = ref("");
const currentUser = ref(getCurrentUser());
let timerId = null;

const localMenuRegistry = [
  {
    path: "/console/dashboard",
    label: "工作台",
    icon: DataLine
  },
  {
    path: "/console/alerts",
    label: "告警中心",
    icon: Bell
  },
  {
    path: "/console/monitor",
    label: "日志监控",
    icon: Monitor
  },
  {
    path: "/console/disposals",
    label: "处置申请",
    icon: DocumentAdd
  },
  {
    path: "/console/my-records",
    label: "我的处理记录",
    icon: Tickets
  },
  {
    path: "/console/bans",
    label: "封禁审批",
    icon: Lock
  },
  {
    path: "/console/users",
    label: "用户管理",
    icon: UserFilled
  },
  {
    path: "/console/rules",
    label: "规则管理",
    icon: SetUp
  },
  {
    path: "/console/audit",
    label: "审计日志",
    icon: Document
  },
  {
    path: "/console/profile",
    label: "个人中心",
    icon: User
  }
];

const activeMenu = computed(() => route.path);

const currentPageTitle = computed(() => {
  return route.meta?.title || "控制台";
});

const currentRoleLabel = computed(() => {
  return currentUser.value ? getRoleLabel(currentUser.value.role) : "未登录";
});

const sideMenuItems = computed(() => {
  const currentRole = currentUser.value?.role;
  if (!currentRole) {
    return [];
  }

  const authMenuMap = new Map(getMenuItemsByRole(currentRole).map((item) => [item.path, item]));

  return localMenuRegistry.filter((item) => {
    if (item.path === "/console/monitor") {
      return Boolean(currentRole);
    }

    return authMenuMap.has(item.path);
  });
});

function updateCurrentTime() {
  const now = new Date();
  currentTimeText.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(
    now.getDate()
  ).padStart(2, "0")} ${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(
    2,
    "0"
  )}:${String(now.getSeconds()).padStart(2, "0")}`;
}

function handleMenuSelect(index) {
  router.push(index);
}

function handleLogout() {
  // 当前阶段统一复用 auth.js 的登录态清理方法。
  // 这样后续如果登录态字段调整，不需要再回头修改布局层逻辑。
  clearCurrentUser();
  currentUser.value = null;
  router.push("/login");
}

onMounted(() => {
  currentUser.value = getCurrentUser();
  updateCurrentTime();
  timerId = window.setInterval(updateCurrentTime, 1000);
});

onBeforeUnmount(() => {
  if (timerId) {
    window.clearInterval(timerId);
  }
});
</script>

<style scoped>
.layout-page {
  min-height: 100vh;
  background: transparent;
}

.layout-shell {
  min-height: 100vh;
}

.layout-aside {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 251, 255, 0.98));
  border-right: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: 12px 0 32px rgba(15, 23, 42, 0.04);
  padding: 18px 16px;
}

.brand-panel {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 14px 26px;
}

.brand-mark {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: #ffffff;
  background: linear-gradient(135deg, #2b7cff, #36b7ff);
  box-shadow: 0 16px 28px rgba(43, 124, 255, 0.28);
}

.brand-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.brand-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.side-menu {
  border-right: none;
}

:deep(.side-menu .el-menu-item) {
  height: 46px;
  border-radius: 12px;
  margin-bottom: 8px;
  color: var(--text-secondary);
  transition:
    background-color 0.2s ease,
    color 0.2s ease,
    box-shadow 0.2s ease;
}

:deep(.side-menu .el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(43, 124, 255, 0.14), rgba(54, 183, 255, 0.08));
  color: var(--brand-primary);
  box-shadow: inset 0 0 0 1px rgba(43, 124, 255, 0.12);
}

:deep(.side-menu .el-menu-item:hover) {
  background: var(--menu-hover-bg);
  color: var(--text-primary);
}

.aside-user-card {
  margin-top: 22px;
  padding: 16px 14px;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(244, 247, 252, 0.92), rgba(255, 255, 255, 0.96));
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
}

.aside-user-card__label {
  font-size: 12px;
  color: var(--text-secondary);
}

.aside-user-card__name {
  margin-top: 10px;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.aside-user-card__meta {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: var(--text-secondary);
  font-size: 12px;
}

.layout-header {
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(248, 251, 255, 0.94));
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04);
  backdrop-filter: blur(12px);
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.header-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.header-status {
  font-size: 12px;
  color: var(--text-secondary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.header-user {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.header-user__name {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.header-user__role {
  font-size: 12px;
  color: var(--text-secondary);
}

.header-time {
  font-size: 13px;
  color: var(--text-secondary);
}

.layout-main {
  padding: 24px;
  background: transparent;
}

@media (max-width: 960px) {
  .layout-aside {
    width: 88px !important;
    padding: 18px 10px;
  }

  .brand-text {
    display: none;
  }

  .aside-user-card {
    padding: 12px 10px;
  }

  :deep(.side-menu .el-menu-item span) {
    display: none;
  }

  .layout-header {
    padding: 0 16px;
  }

  .header-user {
    display: none;
  }

  .header-time {
    display: none;
  }

  .layout-main {
    padding: 16px;
  }
}
</style>
