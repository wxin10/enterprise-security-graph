<template>
  <div class="user-manage-page app-page">
    <section class="security-panel page-banner">
      <div>
        <h1 class="page-title">用户管理</h1>
        <p class="page-subtitle">
          ????????????????????????????????????????????????????
        </p>
      </div>

      <div class="page-banner__actions">
        <el-button v-if="canManageUsers" type="primary" plain @click="loadPageData">刷新列表</el-button>
        <el-button v-if="currentUser" type="primary" @click="handleBackHome">返回工作台</el-button>
        <el-button v-else type="primary" @click="handleGoLogin">前往登录</el-button>
      </div>
    </section>

    <el-alert
      v-if="currentUser && !canManageUsers"
      title="????????????????????????????"
      type="warning"
      :closable="false"
      show-icon
      class="page-alert"
    />

    <el-row :gutter="18" class="summary-grid">
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">当前身份</div>
          <div class="summary-card__value">{{ currentUser ? currentRoleLabel : "未登录" }}</div>
          <div class="summary-card__hint">????????????????????????</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">纳管账号数</div>
          <div class="summary-card__value summary-card__value--primary">{{ userRecords.length }}</div>
          <div class="summary-card__hint">覆盖管理员与一线分析员账号，方便展示平台内部分工</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">管理员账号</div>
          <div class="summary-card__value summary-card__value--warning">{{ adminCount }}</div>
          <div class="summary-card__hint">高权限账号保持最小化，降低高风险操作面</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">待处理审批</div>
          <div class="summary-card__value summary-card__value--danger">{{ pendingApprovals.length }}</div>
          <div class="summary-card__hint">突出管理员需要执行的授权、停用和岗位变更事项</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="18">
      <el-col :xs="24" :xl="16">
        <section class="security-panel filter-panel">
          <div class="section-header">
            <div>
              <h3>账号筛选</h3>
              <p>???????????????????????????????</p>
            </div>
          </div>

          <el-form :inline="true" :model="filterForm" class="filter-form">
            <el-form-item label="角色">
              <el-select v-model="filterForm.role" clearable placeholder="全部角色" style="width: 160px">
                <el-option label="管理员" value="admin" />
                <el-option label="普通用户" value="user" />
              </el-select>
            </el-form-item>

            <el-form-item label="状态">
              <el-select v-model="filterForm.status" clearable placeholder="全部状态" style="width: 160px">
                <el-option label="启用" value="启用" />
                <el-option label="停用" value="停用" />
                <el-option label="待审批" value="待审批" />
              </el-select>
            </el-form-item>

            <el-form-item label="关键字">
              <el-input
                v-model="filterForm.keyword"
                clearable
                placeholder="输入姓名 / 账号 / 部门"
                style="width: 260px"
              />
            </el-form-item>
          </el-form>
        </section>

        <section class="security-panel table-panel">
          <div class="section-header">
            <div>
              <h3>账号列表</h3>
              <p>页面强调管理员职责是“管理账号与权限”，而不是独占告警、图谱等公共业务页面。</p>
            </div>
            <div class="table-header-tip">?????? {{ filteredUsers.length }} ???</div>
          </div>

          <el-table :data="filteredUsers" empty-text="暂无匹配账号">
            <el-table-column prop="display_name" label="姓名" min-width="120" />
            <el-table-column prop="username" label="账号" min-width="120" />
            <el-table-column prop="department" label="部门" min-width="160" />
            <el-table-column label="角色" min-width="110">
              <template #default="{ row }">
                <el-tag :type="roleTagType(row.role)" effect="dark">
                  {{ getRoleLabel(row.role) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="账号状态" min-width="110">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)" effect="plain">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="岗位职责" min-width="220" show-overflow-tooltip />
            <el-table-column prop="last_login_at" label="最近登录" min-width="170" />
            <el-table-column label="操作" min-width="220" fixed="right">
              <template #default="{ row }">
                <div class="table-actions">
                  <el-button link type="primary" @click="handlePreviewScope(row)">权限范围</el-button>
                  <el-button link type="primary" :disabled="!canManageUsers" @click="handleResetAccount(row)">
                    重置口令
                  </el-button>
                  <el-button link type="danger" :disabled="!canManageUsers" @click="handleToggleStatus(row)">
                    {{ row.status === "停用" ? "启用账号" : "停用账号" }}
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </el-col>

      <el-col :xs="24" :xl="8">
        <section class="security-panel side-panel">
          <div class="section-header">
            <div>
              <h3>角色边界说明</h3>
              <p>用于清楚说明管理员和普通用户的差异点，避免把普通用户误做成访客模式。</p>
            </div>
          </div>

          <div class="tip-list">
            <div class="tip-item">
              <div class="tip-item__title">????????????</div>
              <div class="tip-item__desc">????????????????????????????????????</div>
            </div>
            <div class="tip-item">
              <div class="tip-item__title">管理员负责高风险动作</div>
              <div class="tip-item__desc">只有管理员可管理账号、调整角色权限、审批封禁并修改关键规则。</div>
            </div>
            <div class="tip-item">
              <div class="tip-item__title">账号治理强调最小权限</div>
              <div class="tip-item__desc">管理员数量受控，普通用户默认维持业务研判与申请能力，不放大权限。</div>
            </div>
          </div>
        </section>

        <section class="security-panel side-panel">
          <div class="section-header">
            <div>
              <h3>待审批事项</h3>
              <p>展示岗位调整与账号停用等管理员事项，形成管理端页面的最小可演示闭环。</p>
            </div>
          </div>

          <div v-if="pendingApprovals.length > 0" class="approval-list">
            <div v-for="item in pendingApprovals" :key="item.id" class="approval-card">
              <div class="approval-card__header">
                <div class="approval-card__title">{{ item.title }}</div>
                <el-tag size="small" :type="statusTagType(item.status)" effect="dark">
                  {{ item.status }}
                </el-tag>
              </div>
              <div class="approval-card__meta">申请人：{{ item.applicant }}</div>
              <div class="approval-card__meta">影响对象：{{ item.target }}</div>
              <div class="approval-card__meta">提交时间：{{ item.created_at }}</div>
            </div>
          </div>

          <el-empty v-else description="???????????" />
        </section>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
// 文件路径：frontend/src/views/UserManageView.vue
// 作用说明：
// 1. 补齐管理员端“用户管理”页面本体，承接角色权限体系中的账号治理能力。
// 2. 明确普通用户仍能访问核心业务页面，管理员的差异主要体现在管理、审批和高风险操作。
// 3. 当前阶段先使用页面内模拟数据完成前端演示，不改动现有路由、布局和公共权限工具。
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { useRouter } from "vue-router";

import { PERMISSION_KEYS, getCurrentUser, getRoleHomePath, getRoleLabel, hasPermission } from "@/utils/auth";

const MANAGED_USERS = [
  {
    user_id: "ADMIN-001",
    username: "admin",
    display_name: "平台管理员",
    department: "安全运营中心",
    title: "高权限运维负责人",
    role: "admin",
    status: "启用",
    last_login_at: "2026-04-05 01:42:12"
  },
  {
    user_id: "OPS-001",
    username: "analyst",
    display_name: "值班分析员",
    department: "安全运营中心",
    title: "一线运维 / 安全分析员",
    role: "user",
    status: "启用",
    last_login_at: "2026-04-05 01:35:40"
  },
  {
    user_id: "OPS-002",
    username: "reviewer",
    display_name: "研判专员",
    department: "安全运营中心",
    title: "告警复核与处置联络",
    role: "user",
    status: "待审批",
    last_login_at: "2026-04-04 23:18:25"
  },
  {
    user_id: "OPS-003",
    username: "nightwatch",
    display_name: "夜班值守",
    department: "态势感知组",
    title: "夜班告警处置",
    role: "user",
    status: "停用",
    last_login_at: "2026-04-03 22:07:58"
  }
];

const PENDING_APPROVAL_ITEMS = [
  {
    id: "APP-001",
    title: "岗位转岗后降级管理员权限",
    applicant: "人事接口同步任务",
    target: "nightwatch / OPS-003",
    status: "待审批",
    created_at: "2026-04-05 00:48:00"
  },
  {
    id: "APP-002",
    title: "新值班分析员开通普通用户账号",
    applicant: "安全运营中心",
    target: "reviewer / OPS-002",
    status: "待审批",
    created_at: "2026-04-04 21:30:00"
  }
];

const router = useRouter();

const currentUser = ref(null);
const userRecords = ref([]);
const pendingApprovals = ref([]);

const filterForm = reactive({
  role: "",
  status: "",
  keyword: ""
});

const currentRoleLabel = computed(() => {
  return currentUser.value ? getRoleLabel(currentUser.value.role) : "未登录";
});

const canManageUsers = computed(() => {
  return hasPermission(currentUser.value, PERMISSION_KEYS.USER_MANAGE);
});

const adminCount = computed(() => {
  return userRecords.value.filter((item) => item.role === "admin").length;
});

const filteredUsers = computed(() => {
  const keyword = String(filterForm.keyword || "").trim().toLowerCase();

  return userRecords.value.filter((item) => {
    if (filterForm.role && item.role !== filterForm.role) {
      return false;
    }

    if (filterForm.status && item.status !== filterForm.status) {
      return false;
    }

    if (!keyword) {
      return true;
    }

    const haystack = [item.display_name, item.username, item.department, item.title]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return haystack.includes(keyword);
  });
});

function loadPageData() {
  currentUser.value = getCurrentUser();
  userRecords.value = MANAGED_USERS.map((item) => ({ ...item }));
  pendingApprovals.value = PENDING_APPROVAL_ITEMS.map((item) => ({ ...item }));
}

function roleTagType(role) {
  return role === "admin" ? "danger" : "primary";
}

function statusTagType(status) {
  if (status === "启用") {
    return "success";
  }

  if (status === "停用") {
    return "info";
  }

  return "warning";
}

function handlePreviewScope(row) {
  const scopeText =
    row.role === "admin"
      ? "??????????????????"
      : "?????????????????????????";
  ElMessage.info(`${row.display_name}：${scopeText}`);
}

function handleResetAccount(row) {
  if (!canManageUsers.value) {
    ElMessage.warning("??????????????");
    return;
  }

  ElMessage.success(`${row.display_name} ?????????${row.status}?`);
}

function handleToggleStatus(row) {
  if (!canManageUsers.value) {
    ElMessage.warning("当前账号不具备用户管理权限");
    return;
  }

  row.status = row.status === "停用" ? "启用" : "停用";
  ElMessage.success(`${row.display_name} 当前状态已切换为“${row.status}”`);
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

onMounted(() => {
  loadPageData();
});
</script>

<style scoped>
.user-manage-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-banner,
.summary-card,
.filter-panel,
.table-panel,
.side-panel {
  padding: 20px;
}

.page-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.98), var(--page-bg-accent));
}

.page-banner__actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.page-alert {
  margin-top: -4px;
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
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.7;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.section-header h3 {
  margin: 0;
  font-size: 18px;
  color: var(--text-primary);
}

.section-header p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 0;
}

.table-header-tip {
  color: var(--text-secondary);
  font-size: 13px;
}

.table-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
}

.tip-list,
.approval-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tip-item,
.approval-card {
  padding: 14px;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.98));
  border: 1px solid var(--panel-border);
}

.tip-item__title,
.approval-card__title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.tip-item__desc,
.approval-card__meta {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
}

.approval-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

@media (max-width: 992px) {
  .page-banner,
  .section-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
