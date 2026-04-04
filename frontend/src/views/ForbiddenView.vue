<template>
  <div class="forbidden-page app-page">
    <section class="security-panel forbidden-hero">
      <div class="forbidden-hero__content">
        <div class="forbidden-hero__icon">
          <el-icon><Lock /></el-icon>
        </div>
        <div>
          <h1 class="page-title">无权限访问</h1>
          <p class="page-subtitle">
            当前页面属于管理员专属能力范围。核心安全业务页面仍对管理员和普通用户开放，但用户管理、规则管理、
            审批执行和完整审计日志只允许高权限运维负责人操作。
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
          <div class="summary-card__label">当前登录角色</div>
          <div class="summary-card__value">{{ currentUser ? currentRoleLabel : "未登录" }}</div>
          <div class="summary-card__hint">
            {{ currentUser ? "基于当前角色展示可访问范围与限制原因" : "未登录状态下无法访问控制台页面" }}
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :md="8">
        <div class="security-panel summary-card">
          <div class="summary-card__label">被拦截页面</div>
          <div class="summary-card__value summary-card__value--path">{{ requestedPath }}</div>
          <div class="summary-card__hint">如为手动输入管理员地址，将自动建议返回当前角色首页</div>
        </div>
      </el-col>

      <el-col :xs="24" :md="8">
        <div class="security-panel summary-card">
          <div class="summary-card__label">当前可见菜单数</div>
          <div class="summary-card__value">{{ availableMenus.length }}</div>
          <div class="summary-card__hint">普通用户仍可访问工作台、告警中心、图谱分析、申请与个人中心</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="18">
      <el-col :xs="24" :lg="13">
        <section class="security-panel detail-panel">
          <div class="section-header">
            <div>
              <h3>当前角色仍可继续处理的业务</h3>
              <p>以下入口属于当前角色的正常业务范围，不会因为访问受限而失去核心研判能力。</p>
            </div>
          </div>

          <div v-if="availableMenus.length > 0" class="menu-grid">
            <div v-for="item in availableMenus" :key="item.path" class="menu-item">
              <div class="menu-item__label">{{ item.label }}</div>
              <div class="menu-item__path">{{ item.path }}</div>
            </div>
          </div>

          <el-empty v-else description="当前没有可展示的业务菜单，请先登录。" />
        </section>
      </el-col>

      <el-col :xs="24" :lg="11">
        <section class="security-panel detail-panel">
          <div class="section-header">
            <div>
              <h3>本次受限原因</h3>
              <p>受限的不是核心业务查看能力，而是高风险管理与审批能力。</p>
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
          <p>如果你是一线运维或值班分析员，建议回到可用业务页继续研判，并在需要时发起处置申请。</p>
        </div>
      </div>

      <el-steps :active="currentUser ? 2 : 1" finish-status="success" simple>
        <el-step title="确认角色" description="检查当前登录身份与页面权限边界" />
        <el-step title="回到业务页" description="继续处理告警、图谱分析和处置申请" />
        <el-step title="必要时升级" description="需要最终审批或配置变更时联系管理员" />
      </el-steps>
    </section>
  </div>
</template>

<script setup>
// 文件路径：frontend/src/views/ForbiddenView.vue
// 作用说明：
// 1. 承接普通用户误入管理员页面时的解释与返回入口。
// 2. 明确普通用户仍是业务处理角色，而不是访客或只读账号。
// 3. 通过角色菜单与限制清单，让答辩演示时能直接说明权限边界。
import { computed } from "vue";
import { Lock } from "@element-plus/icons-vue";
import { useRoute, useRouter } from "vue-router";

import { getCurrentUser, getMenuItemsByRole, getRoleHomePath, getRoleLabel } from "@/utils/auth";

const router = useRouter();
const route = useRoute();

const RESTRICTED_ACTIONS = [
  {
    title: "系统用户管理",
    description: "创建、停用、调整账号角色属于管理员职责，普通用户不能修改平台成员权限。"
  },
  {
    title: "识别规则与封禁规则管理",
    description: "规则改动会直接影响检测结果与联动处置，必须由高权限运维负责人统一维护。"
  },
  {
    title: "最终封禁 / 解封执行",
    description: "普通用户可以发起申请并填写处置意见，但最终执行需要管理员审批和落地。"
  },
  {
    title: "完整审计日志查看",
    description: "平台级审计信息覆盖全员操作记录，默认只向管理员开放。"
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
  background: linear-gradient(135deg, rgba(255, 124, 124, 0.18), rgba(255, 180, 92, 0.12));
  color: #ff8a7a;
  font-size: 28px;
  box-shadow: inset 0 0 0 1px rgba(255, 145, 121, 0.12);
}

.forbidden-hero__actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.summary-grid :deep(.el-col) {
  margin-bottom: 18px;
}

.summary-card__label {
  font-size: 13px;
  color: #8aa3c8;
}

.summary-card__value {
  margin-top: 12px;
  font-size: 28px;
  font-weight: 700;
  color: #eef5ff;
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
  color: #7f98be;
}

.section-header {
  margin-bottom: 16px;
}

.section-header h3 {
  margin: 0;
  font-size: 18px;
  color: #ecf4ff;
}

.section-header p {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: #8aa3c8;
}

.menu-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.menu-item {
  padding: 14px;
  border-radius: 16px;
  background: rgba(10, 26, 48, 0.72);
  border: 1px solid rgba(101, 146, 219, 0.12);
}

.menu-item__label {
  font-size: 15px;
  font-weight: 700;
  color: #eef5ff;
}

.menu-item__path {
  margin-top: 8px;
  font-size: 12px;
  color: #7f98be;
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
  background: rgba(58, 24, 24, 0.38);
  border: 1px solid rgba(255, 120, 120, 0.14);
}

.restricted-item__title {
  font-size: 15px;
  font-weight: 700;
  color: #ffd7cf;
}

.restricted-item__desc {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: #d7b3ad;
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
