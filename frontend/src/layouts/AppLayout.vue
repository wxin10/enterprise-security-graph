<template>
  <!--
    文件路径：frontend/src/layouts/AppLayout.vue
    作用说明：
    1. 提供系统主布局，采用左侧菜单 + 顶部栏 + 内容区结构。
    2. 承载仪表盘、告警管理、封禁管理与日志监控中心等业务页面。
    3. 当前阶段保持静态登录跳转，不接入真实权限系统。
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
          text-color="#8fa7ca"
          active-text-color="#f3f7ff"
          @select="handleMenuSelect"
        >
          <el-menu-item index="/console/dashboard">
            <el-icon><DataLine /></el-icon>
            <span>仪表盘</span>
          </el-menu-item>

          <el-menu-item index="/console/alerts">
            <el-icon><Bell /></el-icon>
            <span>告警管理</span>
          </el-menu-item>

          <el-menu-item index="/console/bans">
            <el-icon><Lock /></el-icon>
            <span>封禁管理</span>
          </el-menu-item>

          <el-menu-item index="/console/monitor">
            <el-icon><Monitor /></el-icon>
            <span>日志监控</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <el-container>
        <el-header class="layout-header">
          <div class="header-left">
            <div class="header-title">{{ currentPageTitle }}</div>
            <div class="header-status">
              <span class="status-dot status-dot--success"></span>
              当前前后端接口联调正常，可直接展示 Neo4j 图数据与自动化监控流程
            </div>
          </div>

          <div class="header-right">
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
// 2. 根据当前路由同步菜单高亮和页面标题。
// 3. 通过定时器更新时间，增强企业安全控制台的在线监控氛围。
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";

const router = useRouter();
const route = useRoute();

const currentTimeText = ref("");
let timerId = null;

const activeMenu = computed(() => route.path);

const currentPageTitle = computed(() => {
  return route.meta?.title || "控制台";
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
  // 当前阶段不实现真实登录鉴权。
  // 这里仅清理静态登录标记并回到登录页，保持演示流程完整。
  sessionStorage.removeItem("mock_login_user");
  router.push("/login");
}

onMounted(() => {
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
  background:
    linear-gradient(180deg, rgba(7, 18, 33, 0.98), rgba(6, 14, 27, 0.98)),
    var(--menu-bg);
  border-right: 1px solid rgba(71, 114, 176, 0.12);
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
  color: #eef5ff;
}

.brand-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: #7b93b9;
}

.side-menu {
  border-right: none;
}

:deep(.side-menu .el-menu-item) {
  height: 46px;
  border-radius: 12px;
  margin-bottom: 8px;
}

:deep(.side-menu .el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(43, 124, 255, 0.22), rgba(54, 183, 255, 0.14));
  box-shadow: inset 0 0 0 1px rgba(90, 144, 245, 0.12);
}

:deep(.side-menu .el-menu-item:hover) {
  background: var(--menu-hover-bg);
}

.layout-header {
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  background: var(--topbar-bg);
  border-bottom: 1px solid rgba(80, 121, 181, 0.12);
  backdrop-filter: blur(8px);
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.header-title {
  font-size: 20px;
  font-weight: 700;
  color: #eef5ff;
}

.header-status {
  font-size: 12px;
  color: #89a3ca;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.header-time {
  font-size: 13px;
  color: #9fb4d5;
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

  :deep(.side-menu .el-menu-item span) {
    display: none;
  }

  .layout-header {
    padding: 0 16px;
  }

  .header-time {
    display: none;
  }

  .layout-main {
    padding: 16px;
  }
}
</style>
