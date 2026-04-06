<template>
  <div class="forbidden-page app-page">
    <section class="security-panel forbidden-hero">
      <div class="forbidden-hero__content">
        <div class="forbidden-hero__icon">
          <el-icon><Lock /></el-icon>
        </div>
        <div>
          <h1 class="page-title">访问受限</h1>
          <p class="page-subtitle">
            当前页面涉及高权限管理或审批操作，暂不向当前账号开放。核心业务查看、研判和申请入口仍可按角色范围继续使用。
          </p>
        </div>
      </div>

      <div class="forbidden-hero__actions">
        <el-button v-if="currentUser" type="primary" @click="handleBackHome">
          返回工作台
        </el-button>
        <el-button v-if="currentUser" @click="handleGoProfile">
          查看个人中心
        </el-button>
        <el-button v-else type="primary" @click="handleGoLogin">
          前往登录
        </el-button>
      </div>
    </section>

    <el-row :gutter="18" class="summary-grid">
      <el-col :xs="24" :md="8">
        <div class="security-panel summary-card">
          <div class="summary-card__label">当前角色</div>
          <div class="summary-card__value">{{ currentUser ? currentRoleLabel : "未登录" }}</div>
          <div class="summary-card__hint">
            {{ currentUser ? "当前页面权限已按账号职责范围校验。" : "登录后可查看当前账号对应的可访问范围。" }}
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :md="8">
        <div class="security-panel summary-card">
          <div class="summary-card__label">受限页面</div>
          <div class="summary-card__value summary-card__value--path">{{ requestedPath }}</div>
          <div class="summary-card__hint">当前路径未向本账号开放，建议返回角色首页继续处理相关业务。</div>
        </div>
      </el-col>

      <el-col :xs="24" :md="8">
        <div class="security-panel summary-card">
          <div class="summary-card__label">可访问入口</div>
          <div class="summary-card__value">{{ availableMenus.length }}</div>
          <div class="summary-card__hint">当前账号仍可继续使用已授权的业务入口开展日常处置工作。</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="18">
      <el-col :xs="24" :lg="13">
        <section class="security-panel detail-panel">
          <div class="section-header">
            <div>
              <h3>可继续访问的业务入口</h3>
              <p>以下入口仍在当前角色授权范围内，可继续用于查看告警、分析图谱和提交处置申请。</p>
            </div>
          </div>

          <div v-if="availableMenus.length > 0" class="menu-grid">
            <div v-for="item in availableMenus" :key="item.path" class="menu-item">
              <div class="menu-item__label">{{ item.label }}</div>
              <div class="menu-item__path">{{ item.path }}</div>
            </div>
          </div>

          <el-empty v-else description="当前暂无可用入口，请先登录。" />
        </section>
      </el-col>

      <el-col :xs="24" :lg="11">
        <section class="security-panel detail-panel">
          <div class="section-header">
            <div>
              <h3>访问受限原因</h3>
              <p>本次限制针对高权限管理、规则维护和最终审批执行，不影响当前角色已授权的核心业务使用范围。</p>
            </div>
          </div>

          <div class="restricted-list">
            <div v-for="item in restrictedActions" :key="item.title" class="restricted-item">
              <div class="restricted-item__title">{{ item.title }}</div>
              <div class="restricted-item__desc">{{ item.description }}</div>
            </div>
          </div>
        </section>
      </el-col>
    </el-row>

    <section class="security-panel suggestion-panel">
      <div class="section-header">
        <div>
          <h3>建议操作</h3>
          <p>请先确认当前账号职责范围，并返回已授权页面继续处理业务；如确需执行受限操作，请按流程提交申请或联系管理员。</p>
        </div>
      </div>

      <el-steps :active="currentUser ? 2 : 1" finish-status="success" simple>
        <el-step title="确认当前角色" description="核对当前登录身份与页面访问范围" />
        <el-step title="返回业务入口" description="继续处理告警、图谱分析和处置申请等工作" />
        <el-step title="发起协同处理" description="涉及审批、配置或最终执行时联系管理员处理" />
      </el-steps>
    </section>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { Lock } from "@element-plus/icons-vue";
import { useRoute, useRouter } from "vue-router";

import { getCurrentUser, getMenuItemsByRole, getRoleHomePath, getRoleLabel } from "@/utils/auth";

const router = useRouter();
const route = useRoute();

const RESTRICTED_ACTIONS = [
  {
    title: "系统用户管理",
    description: "账号创建、停用和角色调整属于平台管理职责，当前账号不提供相关变更权限。"
  },
  {
    title: "识别规则与封禁规则维护",
    description: "规则变更会直接影响识别结果与联动处置，需由具备管理职责的账号统一维护。"
  },
  {
    title: "最终封禁与解封执行",
    description: "当前账号可提交申请和处置意见，最终执行需经管理员审核并完成落地。"
  },
  {
    title: "完整审计日志查看",
    description: "平台级审计信息覆盖全量操作记录，默认仅向具备相应职责的账号开放。"
  }
];

const currentUser = computed(() => getCurrentUser());

const currentRoleLabel = computed(() => {
  return currentUser.value ? getRoleLabel(currentUser.value.role) : "未登录";
});

const requestedPath = computed(() => {
  const rawPath = route.query.from || route.fullPath;
  return String(rawPath || "/console");
});

const availableMenus = computed(() => {
  if (!currentUser.value) {
    return [];
  }

  return getMenuItemsByRole(currentUser.value.role);
});

const restrictedActions = computed(() => {
  return currentUser.value ? RESTRICTED_ACTIONS : RESTRICTED_ACTIONS.slice(0, 2);
});

function handleBackHome() {
  if (!currentUser.value) {
    router.push("/login");
    return;
  }

  router.push(getRoleHomePath(currentUser.value.role));
}

function handleGoProfile() {
  router.push("/console/profile");
}

function handleGoLogin() {
  router.push("/login");
}
</script>

<style scoped>
.forbidden-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.forbidden-hero,
.summary-card,
.detail-panel,
.suggestion-panel {
  padding: 22px;
}

.forbidden-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(244, 247, 252, 0.94));
}

.forbidden-hero__content {
  display: flex;
  align-items: center;
  gap: 18px;
}

.forbidden-hero__icon {
  width: 64px;
  height: 64px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(255, 113, 88, 0.14), rgba(255, 188, 107, 0.1));
  color: #f97316;
  font-size: 28px;
  box-shadow: inset 0 0 0 1px rgba(249, 115, 22, 0.12);
}

.forbidden-hero__actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.summary-grid :deep(.el-col) {
  margin-bottom: 18px;
}

.summary-card {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(245, 248, 252, 0.96));
}

.summary-card__label {
  font-size: 13px;
  color: var(--text-secondary);
}

.summary-card__value {
  margin-top: 12px;
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}

.summary-card__value--path {
  font-size: 18px;
  line-height: 1.6;
  word-break: break-all;
}

.summary-card__hint {
  margin-top: 10px;
  font-size: 12px;
  line-height: 1.8;
  color: var(--text-secondary);
}

.section-header {
  margin-bottom: 16px;
}

.section-header h3 {
  margin: 0;
  font-size: 18px;
  color: var(--text-primary);
}

.section-header p {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
}

.menu-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.menu-item {
  padding: 14px;
  border-radius: 16px;
  background: var(--page-bg-accent);
  border: 1px solid var(--panel-border);
}

.menu-item__label {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.menu-item__path {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  word-break: break-all;
}

.restricted-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.restricted-item {
  padding: 14px;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(255, 247, 237, 0.88), rgba(255, 255, 255, 0.96));
  border: 1px solid rgba(251, 146, 60, 0.18);
}

.restricted-item__title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.restricted-item__desc {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
}

:deep(.el-steps.is-simple) {
  background: var(--page-bg-accent);
  border: 1px solid var(--panel-border);
  border-radius: 16px;
  padding: 16px;
}

:deep(.el-step__title) {
  color: var(--text-primary) !important;
}

:deep(.el-step__description) {
  color: var(--text-secondary) !important;
}

@media (max-width: 992px) {
  .forbidden-hero {
    flex-direction: column;
    align-items: flex-start;
  }

  .menu-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .forbidden-hero__content {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
