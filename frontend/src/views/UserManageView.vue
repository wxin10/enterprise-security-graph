<template>
  <div class="user-manage-page app-page">
    <section class="security-panel page-banner">
      <div>
        <h1 class="page-title">用户管理</h1>
        <p class="page-subtitle">
          用于统一维护平台账号、角色分工和启停状态，确保账号治理、权限边界与审批流转清晰可控。
        </p>
      </div>

      <div class="page-banner__actions">
        <el-button v-if="canManageUsers" type="primary" plain :loading="loading" @click="loadPageData">刷新列表</el-button>
        <el-button v-if="currentUser" type="primary" @click="handleBackHome">返回工作台</el-button>
        <el-button v-else type="primary" @click="handleGoLogin">前往登录</el-button>
      </div>
    </section>

    <el-alert
      v-if="currentUser && !canManageUsers"
      title="当前账号仅可查看账号治理范围，如需执行用户管理操作，请使用管理员账号登录。"
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
          <div class="summary-card__hint">用于确认当前账号在用户治理、审批流转和高风险操作中的权限边界。</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">纳管账号数</div>
          <div class="summary-card__value summary-card__value--primary">{{ userRecords.length }}</div>
          <div class="summary-card__hint">覆盖管理员与一线分析员账号，便于统一掌握平台账号治理情况。</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">管理员账号</div>
          <div class="summary-card__value summary-card__value--warning">{{ adminCount }}</div>
          <div class="summary-card__hint">高权限账号保持最小化，降低高风险操作面。</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">待处理审批</div>
          <div class="summary-card__value summary-card__value--danger">{{ pendingApprovals.length }}</div>
          <div class="summary-card__hint">聚焦需要管理员确认的账号开通与治理事项。</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="18">
      <el-col :xs="24" :xl="16">
        <section class="security-panel filter-panel">
          <div class="section-header">
            <div>
              <h3>账号筛选</h3>
              <p>支持按角色、状态和关键字筛选平台账号，便于快速定位目标账号与治理对象。</p>
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
          <div class="section-header" style="margin-bottom: 12px;">
            <div>
              <h3>账号列表</h3>
              <p>集中处理账号资料维护、角色边界调整与状态治理。</p>
            </div>
          </div>

          <div class="section-toolbar" style="display: flex; justify-content: flex-end; align-items: center; gap: 16px; margin-bottom: 16px; flex-wrap: wrap;">
            <div class="table-header-tip">当前筛选结果：{{ filteredUsers.length }} 个账号</div>
            <el-button v-if="canManageUsers" type="primary" @click="openCreateDialog">新增账号</el-button>
          </div>

          <el-table v-loading="loading" :data="filteredUsers" empty-text="暂无匹配账号">
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
            <el-table-column label="操作" min-width="280" fixed="right">
              <template #default="{ row }">
                <div class="table-actions">
                  <el-button link type="primary" @click="handlePreviewScope(row)">权限范围</el-button>
                  <el-button link type="primary" :disabled="!canManageUsers" @click="openEditDialog(row)">编辑</el-button>
                  <el-button link type="primary" :disabled="!canManageUsers" @click="handleResetAccount(row)">重置口令</el-button>
                  <el-button link type="danger" :disabled="!canManageUsers" @click="handleToggleStatus(row)">
                    {{ toggleActionLabel(row) }}
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
              <p>用于清晰说明管理员和普通用户的差异点，避免把普通用户误做成访客模式。</p>
            </div>
          </div>

          <div class="tip-list">
            <div class="tip-item">
              <div class="tip-item__title">普通用户参与核心业务处理</div>
              <div class="tip-item__desc">普通用户可访问工作台、检测结果、告警中心、图谱分析等核心业务页面，用于日常研判与处置申请。</div>
            </div>
            <div class="tip-item">
              <div class="tip-item__title">管理员负责高风险治理动作</div>
              <div class="tip-item__desc">只有管理员可管理账号、调整角色权限、审批封禁并修改关键规则。</div>
            </div>
            <div class="tip-item">
              <div class="tip-item__title">账号治理强调最小权限</div>
              <div class="tip-item__desc">管理员数量受控，普通用户默认保留业务研判与申请能力，不放大权限。</div>
            </div>
          </div>
        </section>

        <section class="security-panel side-panel">
          <div class="section-header">
            <div>
              <h3>待审批事项</h3>
              <p>展示账号开通与治理待办，便于管理员统一跟踪待处理任务。</p>
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
              <div class="approval-card__meta">申请来源：{{ item.applicant }}</div>
              <div class="approval-card__meta">影响对象：{{ item.target }}</div>
              <div class="approval-card__meta">提交时间：{{ item.created_at }}</div>
            </div>
          </div>

          <el-empty v-else description="当前暂无待审批事项" />
        </section>
      </el-col>
    </el-row>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新增账号' : '编辑账号'"
      width="640px"
      destroy-on-close
    >
      <el-form ref="dialogFormRef" :model="dialogForm" :rules="dialogRules" label-width="96px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="登录账号" prop="username">
              <el-input v-model="dialogForm.username" :disabled="dialogMode === 'edit'" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="姓名" prop="display_name">
              <el-input v-model="dialogForm.display_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="角色" prop="role">
              <el-select v-model="dialogForm.role" style="width: 100%">
                <el-option label="管理员" value="admin" />
                <el-option label="普通用户" value="user" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-select v-model="dialogForm.status" style="width: 100%">
                <el-option label="启用" value="启用" />
                <el-option label="停用" value="停用" />
                <el-option label="待审批" value="待审批" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="部门" prop="department">
              <el-input v-model="dialogForm.department" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="岗位职责" prop="title">
              <el-input v-model="dialogForm.title" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱">
              <el-input v-model="dialogForm.email" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="手机号">
              <el-input v-model="dialogForm.phone" />
            </el-form-item>
          </el-col>
          <el-col v-if="dialogMode === 'create'" :span="24">
            <el-form-item label="初始密码" prop="password">
              <el-input v-model="dialogForm.password" show-password />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="资料说明">
              <el-input v-model="dialogForm.bio" type="textarea" :rows="3" maxlength="120" show-word-limit />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <div class="dialog-actions">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="handleSubmitDialog">保存</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRouter } from "vue-router";

import { createUser, fetchUsers, resetUserPassword, toggleUserStatus, updateUser } from "@/api/users";
import { PERMISSION_KEYS, getCurrentUser, getRoleHomePath, getRoleLabel, hasPermission } from "@/utils/auth";

const router = useRouter();

const currentUser = ref(null);
const loading = ref(false);
const submitting = ref(false);
const userRecords = ref([]);
const pendingApprovals = ref([]);
const dialogVisible = ref(false);
const dialogMode = ref("create");
const editingUserId = ref("");
const dialogFormRef = ref(null);

const filterForm = reactive({
  role: "",
  status: "",
  keyword: ""
});

const dialogForm = reactive(createDefaultDialogForm());

const dialogRules = {
  username: [{ required: true, message: "请输入登录账号", trigger: "blur" }],
  display_name: [{ required: true, message: "请输入姓名", trigger: "blur" }],
  role: [{ required: true, message: "请选择角色", trigger: "change" }],
  status: [{ required: true, message: "请选择状态", trigger: "change" }],
  department: [{ required: true, message: "请输入部门", trigger: "blur" }],
  title: [{ required: true, message: "请输入岗位职责", trigger: "blur" }],
  password: [{ required: true, message: "请输入初始密码", trigger: "blur" }]
};

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

function createDefaultDialogForm() {
  return {
    username: "",
    display_name: "",
    role: "user",
    status: "启用",
    department: "",
    title: "",
    email: "",
    phone: "",
    bio: "",
    password: "123456"
  };
}

async function loadPageData() {
  currentUser.value = getCurrentUser();

  if (!canManageUsers.value) {
    userRecords.value = [];
    pendingApprovals.value = [];
    return;
  }

  loading.value = true;

  try {
    const response = await fetchUsers();
    userRecords.value = response.data?.items || [];
    pendingApprovals.value = response.data?.pending_approvals || [];
  } finally {
    loading.value = false;
  }
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

function toggleActionLabel(row) {
  if (row.status === "待审批") {
    return "通过审批";
  }

  return row.status === "停用" ? "启用账号" : "停用账号";
}

function handlePreviewScope(row) {
  const scopeText =
    row.role === "admin"
      ? "可管理平台账号、调整角色权限、审批处置申请，并查看完整审计日志与关键配置。"
      : "可查看核心业务页面、分析告警与图谱、提交处置申请，并查看个人处理记录。";
  ElMessage.info(`${row.display_name}：${scopeText}`);
}

function openCreateDialog() {
  dialogMode.value = "create";
  editingUserId.value = "";
  Object.assign(dialogForm, createDefaultDialogForm());
  dialogVisible.value = true;
}

function openEditDialog(row) {
  dialogMode.value = "edit";
  editingUserId.value = row.user_id;
  Object.assign(dialogForm, {
    username: row.username,
    display_name: row.display_name,
    role: row.role,
    status: row.status,
    department: row.department,
    title: row.title,
    email: row.email || "",
    phone: row.phone || "",
    bio: row.bio || "",
    password: "123456"
  });
  dialogVisible.value = true;
}

async function handleSubmitDialog() {
  await dialogFormRef.value?.validate();
  submitting.value = true;

  try {
    if (dialogMode.value === "create") {
      const response = await createUser(dialogForm);
      ElMessage.success(`${response.message}，初始密码：${response.data?.temporary_password || "123456"}`);
    } else {
      const response = await updateUser(editingUserId.value, dialogForm);
      ElMessage.success(response.message || "账号资料已更新");
    }

    dialogVisible.value = false;
    await loadPageData();
  } finally {
    submitting.value = false;
  }
}

async function handleResetAccount(row) {
  try {
    await ElMessageBox.confirm(`确认重置 ${row.display_name} 的登录密码吗？`, "重置确认", {
      type: "warning"
    });
  } catch (error) {
    return;
  }

  const response = await resetUserPassword(row.user_id);
  ElMessage.success(`${response.message}，初始密码：${response.data?.temporary_password || "123456"}`);
  await loadPageData();
}

async function handleToggleStatus(row) {
  try {
    await ElMessageBox.confirm(`确认处理账号 ${row.display_name} 的状态变更吗？`, "状态确认", {
      type: "warning"
    });
  } catch (error) {
    return;
  }

  const response = await toggleUserStatus(row.user_id);
  ElMessage.success(response.message || "用户状态已更新");
  await loadPageData();
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

.page-banner__actions,
.section-header__actions,
.dialog-actions {
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
