<template>
  <div class="rule-manage-page app-page">
    <section class="security-panel page-banner">
      <div>
        <h1 class="page-title">规则管理</h1>
        <p class="page-subtitle">
          用于管理员统一维护识别规则、封禁策略和变更流程，保障识别链路稳定、可控、可追踪。
        </p>
      </div>

      <div class="page-banner__actions">
        <el-button v-if="canManageRules" type="primary" plain :loading="loading" @click="loadPageData">刷新规则</el-button>
        <el-button v-if="currentUser" type="primary" @click="handleBackHome">返回工作台</el-button>
        <el-button v-else type="primary" @click="handleGoLogin">前往登录</el-button>
      </div>
    </section>

    <el-alert
      v-if="currentUser && !canManageRules"
      title="当前账号不具备规则管理权限，本页仅用于说明管理员侧的规则治理职责边界。"
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
          <div class="summary-card__hint">只有管理员可维护规则体系，普通用户继续聚焦告警分析与申请提交。</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">启用规则数</div>
          <div class="summary-card__value summary-card__value--primary">{{ enabledRuleCount }}</div>
          <div class="summary-card__hint">覆盖识别规则与封禁策略，便于统一掌握当前生效中的规则配置。</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">识别规则</div>
          <div class="summary-card__value summary-card__value--warning">{{ detectionRuleCount }}</div>
          <div class="summary-card__hint">负责恶意行为识别、异常登录检测和攻击链分析支撑。</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">待评估变更</div>
          <div class="summary-card__value summary-card__value--danger">{{ changeQueue.length }}</div>
          <div class="summary-card__hint">聚焦规则调整前仍需复核业务影响范围的治理事项。</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="18">
      <el-col :xs="24" :xl="16">
        <section class="security-panel filter-panel">
          <div class="section-header">
            <div>
              <h3>规则筛选</h3>
              <p>支持按规则类型、状态和关键字快速定位，便于高效核对目标规则。</p>
            </div>
          </div>

          <el-form :inline="true" :model="filterForm" class="filter-form">
            <el-form-item label="规则类型">
              <el-select v-model="filterForm.category" clearable placeholder="全部类型" style="width: 160px">
                <el-option label="识别规则" value="识别规则" />
                <el-option label="封禁规则" value="封禁规则" />
              </el-select>
            </el-form-item>

            <el-form-item label="状态">
              <el-select v-model="filterForm.status" clearable placeholder="全部状态" style="width: 160px">
                <el-option label="启用" value="启用" />
                <el-option label="灰度" value="灰度" />
                <el-option label="停用" value="停用" />
              </el-select>
            </el-form-item>

            <el-form-item label="关键字">
              <el-input
                v-model="filterForm.keyword"
                clearable
                placeholder="输入规则编号 / 名称 / 说明"
                style="width: 280px"
              />
            </el-form-item>
          </el-form>
        </section>

        <section class="security-panel table-panel">
          <div class="section-header" style="margin-bottom: 12px;">
            <div>
              <h3>规则列表</h3>
              <p>集中维护规则阈值、命中效果和状态治理，确保识别链路稳定可控。</p>
            </div>
          </div>

          <div class="section-toolbar" style="display: flex; justify-content: flex-end; align-items: center; gap: 16px; margin-bottom: 16px; flex-wrap: wrap;">
            <div class="table-header-tip">当前命中 {{ filteredRules.length }} 条规则</div>
            <el-button v-if="canManageRules" type="primary" @click="openCreateDialog">新增规则</el-button>
          </div>

          <el-table v-loading="loading" :data="filteredRules" empty-text="暂无匹配规则">
            <el-table-column prop="rule_code" label="规则编号" min-width="150" />
            <el-table-column prop="rule_name" label="规则名称" min-width="220" show-overflow-tooltip />
            <el-table-column label="类型" min-width="110">
              <template #default="{ row }">
                <el-tag :type="categoryTagType(row.category)" effect="dark">
                  {{ row.category }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" min-width="100">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)" effect="plain">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="threshold" label="触发阈值" min-width="180" show-overflow-tooltip />
            <el-table-column prop="hit_count" label="近 24 小时命中" min-width="130" />
            <el-table-column prop="updated_at" label="最近更新时间" min-width="170" />
            <el-table-column label="操作" min-width="260" fixed="right">
              <template #default="{ row }">
                <div class="table-actions">
                  <el-button link type="primary" @click="handlePreviewRule(row)">查看说明</el-button>
                  <el-button link type="primary" :disabled="!canManageRules" @click="openEditDialog(row)">编辑</el-button>
                  <el-button link type="primary" :disabled="!canManageRules" @click="handleGrayRelease(row)">灰度发布</el-button>
                  <el-button link type="danger" :disabled="!canManageRules" @click="handleToggleRule(row)">
                    {{ row.status === "停用" ? "启用规则" : "停用规则" }}
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
              <h3>规则变更流程</h3>
              <p>说明管理员页面的核心职责在于规则治理，而不是替代一线用户的日常研判工作。</p>
            </div>
          </div>

          <div class="tip-list">
            <div class="tip-item">
              <div class="tip-item__title">1. 分析员提出调整建议</div>
              <div class="tip-item__desc">普通用户可以在告警研判后给出处置意见，但不直接修改规则本身。</div>
            </div>
            <div class="tip-item">
              <div class="tip-item__title">2. 管理员评估影响范围</div>
              <div class="tip-item__desc">结合命中量、误报率和业务影响决定是否执行灰度发布。</div>
            </div>
            <div class="tip-item">
              <div class="tip-item__title">3. 再执行最终策略</div>
              <div class="tip-item__desc">只有管理员可启停封禁策略和高风险规则，确保关键配置修改可追踪。</div>
            </div>
          </div>
        </section>

        <section class="security-panel side-panel">
          <div class="section-header">
            <div>
              <h3>待评估变更</h3>
              <p>用于汇总规则调整待办，便于管理员统一跟踪规则变更事项。</p>
            </div>
          </div>

          <div v-if="changeQueue.length > 0" class="change-list">
            <div v-for="item in changeQueue" :key="item.id" class="change-card">
              <div class="change-card__header">
                <div class="change-card__title">{{ item.rule_name }}</div>
                <el-tag size="small" :type="statusTagType(item.status === '待评估' ? '灰度' : '启用')" effect="dark">
                  {{ item.status }}
                </el-tag>
              </div>
              <div class="change-card__meta">建议来源：{{ item.source }}</div>
              <div class="change-card__meta">拟调整内容：{{ item.change_summary }}</div>
              <div class="change-card__meta">提交时间：{{ item.created_at }}</div>
            </div>
          </div>

          <el-empty v-else description="当前没有待评估规则变更" />
        </section>
      </el-col>
    </el-row>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新增规则' : '编辑规则'"
      width="680px"
      destroy-on-close
    >
      <el-form ref="dialogFormRef" :model="dialogForm" :rules="dialogRules" label-width="96px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="规则编号" prop="rule_code">
              <el-input v-model="dialogForm.rule_code" :disabled="dialogMode === 'edit'" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="规则名称" prop="rule_name">
              <el-input v-model="dialogForm.rule_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="规则类型" prop="category">
              <el-select v-model="dialogForm.category" style="width: 100%">
                <el-option label="识别规则" value="识别规则" />
                <el-option label="封禁规则" value="封禁规则" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-select v-model="dialogForm.status" style="width: 100%">
                <el-option label="启用" value="启用" />
                <el-option label="灰度" value="灰度" />
                <el-option label="停用" value="停用" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="触发阈值" prop="threshold">
              <el-input v-model="dialogForm.threshold" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="命中次数" prop="hit_count">
              <el-input-number v-model="dialogForm.hit_count" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="责任人">
              <el-input v-model="dialogForm.owner" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="规则说明" prop="description">
              <el-input v-model="dialogForm.description" type="textarea" :rows="4" maxlength="200" show-word-limit />
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

import { createRule, fetchRules, grayReleaseRule, toggleRuleStatus, updateRule } from "@/api/rules";
import { PERMISSION_KEYS, getCurrentUser, getRoleHomePath, getRoleLabel, hasPermission } from "@/utils/auth";

const router = useRouter();

const currentUser = ref(null);
const loading = ref(false);
const submitting = ref(false);
const ruleItems = ref([]);
const changeQueue = ref([]);
const dialogVisible = ref(false);
const dialogMode = ref("create");
const editingRuleId = ref("");
const dialogFormRef = ref(null);

const filterForm = reactive({
  category: "",
  status: "",
  keyword: ""
});

const dialogForm = reactive(createDefaultDialogForm());

const dialogRules = {
  rule_code: [{ required: true, message: "请输入规则编号", trigger: "blur" }],
  rule_name: [{ required: true, message: "请输入规则名称", trigger: "blur" }],
  category: [{ required: true, message: "请选择规则类型", trigger: "change" }],
  status: [{ required: true, message: "请选择状态", trigger: "change" }],
  threshold: [{ required: true, message: "请输入触发阈值", trigger: "blur" }],
  description: [{ required: true, message: "请输入规则说明", trigger: "blur" }]
};

const currentRoleLabel = computed(() => {
  return currentUser.value ? getRoleLabel(currentUser.value.role) : "未登录";
});

const canManageRules = computed(() => {
  return hasPermission(currentUser.value, PERMISSION_KEYS.RULE_MANAGE);
});

const enabledRuleCount = computed(() => {
  return ruleItems.value.filter((item) => item.status === "启用").length;
});

const detectionRuleCount = computed(() => {
  return ruleItems.value.filter((item) => item.category === "识别规则").length;
});

const filteredRules = computed(() => {
  const keyword = String(filterForm.keyword || "").trim().toLowerCase();

  return ruleItems.value.filter((item) => {
    if (filterForm.category && item.category !== filterForm.category) {
      return false;
    }

    if (filterForm.status && item.status !== filterForm.status) {
      return false;
    }

    if (!keyword) {
      return true;
    }

    const haystack = [item.rule_code, item.rule_name, item.description, item.threshold]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return haystack.includes(keyword);
  });
});

function createDefaultDialogForm() {
  return {
    rule_code: "",
    rule_name: "",
    category: "识别规则",
    status: "停用",
    threshold: "",
    hit_count: 0,
    owner: "",
    description: ""
  };
}

async function loadPageData() {
  currentUser.value = getCurrentUser();

  if (!canManageRules.value) {
    ruleItems.value = [];
    changeQueue.value = [];
    return;
  }

  loading.value = true;

  try {
    const response = await fetchRules();
    ruleItems.value = response.data?.items || [];
    changeQueue.value = response.data?.change_queue || [];
  } finally {
    loading.value = false;
  }
}

function categoryTagType(category) {
  return category === "封禁规则" ? "danger" : "primary";
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

function handlePreviewRule(row) {
  ElMessage.info(`${row.rule_name}：${row.description}`);
}

function openCreateDialog() {
  dialogMode.value = "create";
  editingRuleId.value = "";
  Object.assign(dialogForm, createDefaultDialogForm());
  dialogVisible.value = true;
}

function openEditDialog(row) {
  dialogMode.value = "edit";
  editingRuleId.value = row.id;
  Object.assign(dialogForm, {
    rule_code: row.rule_code,
    rule_name: row.rule_name,
    category: row.category,
    status: row.status,
    threshold: row.threshold,
    hit_count: Number(row.hit_count || 0),
    owner: row.owner || "",
    description: row.description
  });
  dialogVisible.value = true;
}

async function handleSubmitDialog() {
  await dialogFormRef.value?.validate();
  submitting.value = true;

  try {
    if (dialogMode.value === "create") {
      const response = await createRule(dialogForm);
      ElMessage.success(response.message || "规则创建成功");
    } else {
      const response = await updateRule(editingRuleId.value, dialogForm);
      ElMessage.success(response.message || "规则更新成功");
    }

    dialogVisible.value = false;
    await loadPageData();
  } finally {
    submitting.value = false;
  }
}

async function handleGrayRelease(row) {
  try {
    await ElMessageBox.confirm(`确认将 ${row.rule_name} 调整为灰度发布吗？`, "灰度发布确认", {
      type: "warning"
    });
  } catch (error) {
    return;
  }

  const response = await grayReleaseRule(row.id, {
    note: `管理员已对 ${row.rule_name} 执行灰度发布，等待命中效果复核。`
  });
  ElMessage.success(response.message || "规则已进入灰度发布");
  await loadPageData();
}

async function handleToggleRule(row) {
  try {
    await ElMessageBox.confirm(`确认处理规则 ${row.rule_name} 的状态变更吗？`, "状态确认", {
      type: "warning"
    });
  } catch (error) {
    return;
  }

  const response = await toggleRuleStatus(row.id);
  ElMessage.success(response.message || "规则状态已更新");
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
.rule-manage-page {
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
.change-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tip-item,
.change-card {
  padding: 14px;
  border-radius: 16px;
  background: var(--page-bg-accent);
  border: 1px solid var(--panel-border);
}

.tip-item__title,
.change-card__title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.tip-item__desc,
.change-card__meta {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
}

.change-card__header {
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
