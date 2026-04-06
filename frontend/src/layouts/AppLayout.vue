<template>
  <!--
    鏂囦欢璺緞锛歠rontend/src/layouts/AppLayout.vue
    浣滅敤璇存槑锛?    1. 鎻愪緵绯荤粺涓诲竷灞€锛岄噰鐢ㄥ乏渚ц彍鍗?+ 椤堕儴鏍?+ 鍐呭鍖虹粨鏋勩€?    2. 鎵胯浇浠〃鐩樸€佸憡璀︾鐞嗐€佸皝绂佺鐞嗕笌鏃ュ織鐩戞帶涓績绛変笟鍔￠〉闈€?    3. 鍦ㄧ幇鏈夊竷灞€鍩虹涓婃帴鍏ヨ鑹茶彍鍗曘€佺敤鎴蜂俊鎭笌椤甸潰瀹炵幇鐘舵€佽鏄庛€?  -->
  <div class="layout-page">
    <el-container class="layout-shell">
      <el-aside class="layout-aside" width="240px">
        <div class="brand-panel">
          <div class="brand-mark">
            <el-icon><Monitor /></el-icon>
          </div>
          <div class="brand-text">
            <div class="brand-title">浼佷笟瀹夊叏鍥捐氨骞冲彴</div>
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
              <component :is="item.iconComponent" />
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
              {{ currentPageStatusText }}
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
              退出</el-button>
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
// 作用说明：提供控制台主布局、侧边菜单与顶部状态展示。
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { Bell, DataLine, Document, DocumentAdd, Lock, Monitor, SetUp, Tickets, User, UserFilled } from "@element-plus/icons-vue";
import { RouterView, useRoute, useRouter } from "vue-router";
import { clearCurrentSession, getCurrentUser, getMenuItemsByRole, getRoleLabel } from "@/utils/auth";

const router = useRouter();
const route = useRoute();

const currentTimeText = ref("");
const currentUser = ref(getCurrentUser());
let timerId = null;

const menuIconMap = {
  DataLine,
  Bell,
  Monitor,
  DocumentAdd,
  Tickets,
  Lock,
  UserFilled,
  SetUp,
  Document,
  User
};

const activeMenu = computed(() => route.path);

const currentPageTitle = computed(() => {
  return route.meta?.title || "控制台";
});

const currentPageStatusText = computed(() => {
  const statusNote = String(route.meta?.statusNote || "").trim();
  if (statusNote) {
    return statusNote;
  }

  const dataSource = String(route.meta?.dataSource || "").trim();
  if (dataSource === "backend-api") {
    return "当前页面支持业务数据查看与风险处置，请按页面指引完成相关操作。";
  }

  if (dataSource === "local-state") {
    return "当前页面支持信息维护与流程处理，请按职责范围办理相关事项。";
  }

  return "当前页面状态正常，请按业务流程处理相关事项。";
});
const currentRoleLabel = computed(() => {
  return currentUser.value ? getRoleLabel(currentUser.value.role) : "未登录";
});

const sideMenuItems = computed(() => {
  const currentRole = currentUser.value?.role;
  if (!currentRole) {
    return [];
  }

  return getMenuItemsByRole(currentRole).map((item) => ({
    ...item,
    iconComponent: menuIconMap[item.icon] || Monitor
  }));
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
  clearCurrentSession();
  currentUser.value = null;
  router.replace("/login");
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
