<template>
  <div class="profile-page app-page">
    <section class="security-panel profile-hero">
      <div v-if="currentUser" class="profile-hero__content">
        <div class="profile-hero__avatar">
          {{ userInitial }}
        </div>
        <div>
          <div class="profile-hero__role">{{ currentRoleLabel }}</div>
          <h1 class="page-title">{{ currentUser.display_name }}</h1>
          <p class="page-subtitle">
            {{
              [currentUser.title, currentUser.department, "负责当前岗位的安全运营、告警研判与处置跟踪工作。"]
                .filter(Boolean)
                .join("，")
            }}
          </p>
        </div>
      </div>

      <div v-else class="profile-hero__content">
        <div class="profile-hero__avatar">登</div>
        <div>
          <h1 class="page-title">个人中心</h1>
          <p class="page-subtitle">当前未检测到有效登录信息，请登录后查看个人资料、权限边界和最近处置记录。</p>
        </div>
      </div>

      <div class="profile-hero__actions">
        <el-button v-if="currentUser" type="primary" @click="handleBackHome">
          返回工作台
        </el-button>
        <el-button v-else type="primary" @click="handleGoLogin">
          前往登录
        </el-button>
      </div>
    </section>

    <el-row :gutter="18" class="summary-grid">
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">角色身份</div>
          <div class="summary-card__value">{{ currentUser ? currentRoleLabel : "-" }}</div>
          <div class="summary-card__hint">角色身份决定账号可执行的审批、规则管理和审计查看范围</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">权限项目</div>
          <div class="summary-card__value summary-card__value--primary">{{ availablePermissionItems.length }}</div>
          <div class="summary-card__hint">汇总当前账号已开通的业务能力与管理权限范围</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">我的处置记录</div>
          <div class="summary-card__value summary-card__value--warning">{{ myRequestRecords.length }}</div>
          <div class="summary-card__hint">统计当前账号已发起的处置申请与近期跟踪记录</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">待办事项</div>
          <div class="summary-card__value summary-card__value--danger">{{ pendingRequestCount }}</div>
          <div class="summary-card__hint">用于提示当前账号仍需关注的审批流转与后续处理事项</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="18">
      <el-col :xs="24" :lg="10">
        <section class="security-panel detail-panel">
          <div class="section-header">
            <div>
              <h3>基本信息</h3>
              <p>展示当前登录账号的基础资料、岗位信息与最近登录时间。</p>
            </div>
          </div>

          <div v-if="currentUser" class="info-list">
            <div class="info-row">
              <span class="info-row__label">用户编号</span>
              <span class="info-row__value">{{ currentUser.user_id }}</span>
            </div>
            <div class="info-row">
              <span class="info-row__label">登录账号</span>
              <span class="info-row__value">{{ currentUser.username }}</span>
            </div>
            <div class="info-row">
              <span class="info-row__label">姓名</span>
              <span class="info-row__value">{{ currentUser.display_name }}</span>
            </div>
            <div class="info-row">
              <span class="info-row__label">所属部门</span>
              <span class="info-row__value">{{ currentUser.department }}</span>
            </div>
            <div class="info-row">
              <span class="info-row__label">岗位职责</span>
              <span class="info-row__value">{{ currentUser.title }}</span>
            </div>
            <div class="info-row">
              <span class="info-row__label">最近登录时间</span>
              <span class="info-row__value">{{ formattedLoginAt }}</span>
            </div>
          </div>

          <el-empty v-else description="当前未登录，无法查看个人资料" />
        </section>
      </el-col>

      <el-col :xs="24" :lg="14">
        <section class="security-panel detail-panel">
          <div class="section-header">
            <div>
              <h3>权限边界</h3>
              <p>集中展示当前账号可执行与受限的能力范围，便于按职责开展日常处置与管理操作。</p>
            </div>
          </div>

          <div class="permission-layout">
            <div class="permission-block">
              <div class="permission-block__title">当前可执行</div>
              <div v-if="availablePermissionItems.length > 0" class="permission-list">
                <div v-for="item in availablePermissionItems" :key="item.key" class="permission-item permission-item--available">
                  <div class="permission-item__title">{{ item.title }}</div>
                  <div class="permission-item__desc">{{ item.description }}</div>
                </div>
              </div>
              <el-empty v-else description="当前暂无可展示的权限项目" />
            </div>

            <div class="permission-block">
              <div class="permission-block__title">当前受限</div>
              <div v-if="restrictedPermissionItems.length > 0" class="permission-list">
                <div v-for="item in restrictedPermissionItems" :key="item.key" class="permission-item permission-item--restricted">
                  <div class="permission-item__title">{{ item.title }}</div>
                  <div class="permission-item__desc">{{ item.description }}</div>
                </div>
              </div>
              <div v-else class="permission-admin-tip">
                当前账号已具备配置、审批与审计等管理能力，可继续进入相应管理页面执行操作。
              </div>
            </div>
          </div>
        </section>
      </el-col>
    </el-row>

    <section class="security-panel records-panel">
      <div class="section-header">
        <div>
          <h3>最近处置记录</h3>
            <p>展示当前账号最近参与的处置记录，便于跟踪个人处理进度与结果。</p>
        </div>
      </div>

      <el-table :data="recentRecords" empty-text="当前暂无个人处置记录">
        <el-table-column prop="request_id" label="申请编号" min-width="170" />
        <el-table-column prop="alert_name" label="关联告警" min-width="180" show-overflow-tooltip />
        <el-table-column prop="disposal_type" label="处置类型" min-width="120" />
        <el-table-column prop="urgency_level" label="紧急等级" min-width="110" />
        <el-table-column label="当前状态" min-width="110">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" effect="plain">
              {{ row.status || "-" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="最近更新时间" min-width="170" />
      </el-table>
    </section>
  </div>
</template>

<script setup>
// 文件路径：frontend/src/views/ProfileView.vue
// 作用说明：
// 1. 展示当前登录用户的基础资料、角色身份与最近登录时间。
// 2. 基于 auth.js 的权限映射直观区分“可执行”和“受限”能力。
// 3. 复用 mock-storage.js 的本地数据，为后续“我的处理记录”页面铺垫数据来源。
import { computed } from "vue";
import { useRouter } from "vue-router";

import {
  PERMISSION_KEYS,
  getCurrentUser,
  getPermissionList,
  getRoleHomePath,
  getRoleLabel
} from "@/utils/auth";
import { listMyDisposalRequests } from "@/utils/mock-storage";

const router = useRouter();

const PERMISSION_META = [
  {
    key: PERMISSION_KEYS.ALERT_MARK,
    title: "告警查看与标记",
    description: "支持查看、筛选、分析和标记恶意行为告警，是普通用户与管理员共享的核心业务能力。"
  },
  {
    key: PERMISSION_KEYS.DISPOSAL_APPLY,
    title: "发起处置申请",
    description: "允许填写处置意见并提交封禁申请，适用于值班分析员的日常闭环处理。"
  },
  {
    key: PERMISSION_KEYS.DISPOSAL_VIEW_SELF,
    title: "查看个人处理记录",
    description: "查看本人提交的处置申请和处理轨迹，便于回溯历史工作。"
  },
  {
    key: PERMISSION_KEYS.BAN_EXECUTE,
    title: "执行最终封禁 / 解封",
    description: "属于高风险执行动作，仅向管理员开放。"
  },
  {
    key: PERMISSION_KEYS.BAN_VERIFY,
    title: "封禁审批",
    description: "负责审核普通用户提交的处置申请并决定是否执行联动封禁。"
  },
  {
    key: PERMISSION_KEYS.USER_MANAGE,
    title: "系统用户管理",
    description: "维护平台账号、角色和人员启停状态，属于管理员能力。"
  },
  {
    key: PERMISSION_KEYS.RULE_MANAGE,
    title: "规则管理",
    description: "维护识别规则和封禁策略，会直接影响检测链路。"
  },
  {
    key: PERMISSION_KEYS.AUDIT_VIEW,
    title: "完整审计日志查看",
    description: "查看全平台操作留痕，通常只向管理员开放。"
  },
  {
    key: PERMISSION_KEYS.CONFIG_MANAGE,
    title: "关键配置管理",
    description: "修改系统关键配置与联动策略，属于平台管理员职责。"
  }
];

const currentUser = computed(() => getCurrentUser());

const currentRoleLabel = computed(() => {
  return currentUser.value ? getRoleLabel(currentUser.value.role) : "未登录";
});

const userInitial = computed(() => {
  if (!currentUser.value?.display_name) {
    return "登";
  }

  return String(currentUser.value.display_name).trim().slice(0, 1).toUpperCase();
});

const permissionKeys = computed(() => {
  return currentUser.value ? getPermissionList(currentUser.value.role) : [];
});

const availablePermissionItems = computed(() => {
  return PERMISSION_META.filter((item) => permissionKeys.value.includes(item.key));
});

const restrictedPermissionItems = computed(() => {
  return PERMISSION_META.filter((item) => !permissionKeys.value.includes(item.key));
});

const myRequestRecords = computed(() => {
  return currentUser.value ? listMyDisposalRequests(currentUser.value) : [];
});

const pendingRequestCount = computed(() => {
  return myRequestRecords.value.filter((item) => String(item.status || "").includes("待")).length;
});

const recentRecords = computed(() => {
  return myRequestRecords.value.slice(0, 5);
});

const formattedLoginAt = computed(() => {
  const loginAt = currentUser.value?.login_at;
  if (!loginAt) {
    return "-";
  }

  const resolvedDate = new Date(loginAt);
  if (Number.isNaN(resolvedDate.getTime())) {
    return String(loginAt);
  }

  // 统一转为本地展示字符串，避免答辩时看到 ISO 原始格式。
  return resolvedDate.toLocaleString("zh-CN", { hour12: false });
});

function statusTagType(status) {
  if (String(status).includes("通过")) {
    return "success";
  }

  if (String(status).includes("拒绝")) {
    return "danger";
  }

  if (String(status).includes("待")) {
    return "warning";
  }

  return "info";
}

function handleBackHome() {
  if (!currentUser.value) {
    router.push("/login");
    return;
  }

  router.push(getRoleHomePath(currentUser.value.role));
}

function handleGoLogin() {
  router.push("/login");
}
</script>

<style scoped>
.profile-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.profile-hero,
.summary-card,
.detail-panel,
.records-panel {
  padding: 22px;
}

.profile-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.98), var(--page-bg-accent));
}

.profile-hero__content {
  display: flex;
  align-items: center;
  gap: 18px;
}

.profile-hero__avatar {
  width: 68px;
  height: 68px;
  border-radius: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  font-weight: 700;
  color: #ffffff;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.92), rgba(14, 165, 233, 0.86));
  box-shadow: 0 16px 28px rgba(59, 130, 246, 0.18);
}

.profile-hero__role {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.1);
  color: var(--text-primary);
  font-size: 12px;
  margin-bottom: 10px;
  border: 1px solid rgba(59, 130, 246, 0.16);
}

.profile-hero__actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.summary-grid :deep(.el-col) {
  margin-bottom: 18px;
}

.summary-card__label {
  font-size: 13px;
  color: var(--text-secondary);
}

.summary-card__value {
  margin-top: 12px;
  font-size: 30px;
  font-weight: 700;
  color: var(--text-primary);
}

.summary-card__value--primary {
  color: #2563eb;
}

.summary-card__value--warning {
  color: #d97706;
}

.summary-card__value--danger {
  color: #dc2626;
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

.info-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.98));
  border: 1px solid var(--panel-border);
}

.info-row__label {
  color: var(--text-secondary);
  font-size: 13px;
}

.info-row__value {
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
  text-align: right;
  word-break: break-all;
}

.permission-layout {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.permission-block__title {
  margin-bottom: 12px;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.permission-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.permission-item {
  padding: 14px;
  border-radius: 16px;
  border: 1px solid transparent;
}

.permission-item--available {
  background: rgba(14, 165, 233, 0.06);
  border-color: rgba(14, 165, 233, 0.14);
}

.permission-item--restricted {
  background: rgba(239, 68, 68, 0.05);
  border-color: rgba(239, 68, 68, 0.14);
}

.permission-item__title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.permission-item__desc {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
}

.permission-admin-tip {
  padding: 16px;
  border-radius: 16px;
  background: rgba(34, 197, 94, 0.06);
  border: 1px solid rgba(34, 197, 94, 0.14);
  color: var(--text-primary);
  line-height: 1.8;
  font-size: 13px;
}

@media (max-width: 1200px) {
  .permission-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 992px) {
  .profile-hero {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 640px) {
  .profile-hero__content,
  .info-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .info-row__value {
    text-align: left;
  }
}
</style>
