<template>
  <div class="audit-log-page app-page">
    <section class="security-panel page-banner">
      <div>
        <h1 class="page-title">审计日志</h1>
        <p class="page-subtitle">
          用于管理员集中查看处置申请、规则变更、账号治理与高风险操作留痕，确保平台关键动作可追踪、可复盘。
        </p>
      </div>

      <div class="page-banner__actions">
        <el-button v-if="canViewAudit" type="primary" plain :loading="loading" @click="loadPageData">刷新日志</el-button>
        <el-button v-if="currentUser" type="primary" @click="handleBackHome">返回工作台</el-button>
        <el-button v-else type="primary" @click="handleGoLogin">前往登录</el-button>
      </div>
    </section>

    <el-alert
      v-if="currentUser && !canViewAudit"
      title="当前账号不具备完整审计日志查看权限，本页仅用于说明管理员侧的审计职责边界。"
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
          <div class="summary-card__hint">只有管理员可查看完整操作留痕，普通用户继续处理告警分析与处置申请。</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">日志总数</div>
          <div class="summary-card__value summary-card__value--primary">{{ auditRecords.length }}</div>
          <div class="summary-card__hint">汇聚账号治理、规则管理、审批流转与处置申请的关键操作留痕。</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">管理员动作</div>
          <div class="summary-card__value summary-card__value--warning">{{ adminActionCount }}</div>
          <div class="summary-card__hint">突出审批、规则发布、账号调整等只允许管理员执行的关键动作。</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">高风险记录</div>
          <div class="summary-card__value summary-card__value--danger">{{ highRiskCount }}</div>
          <div class="summary-card__hint">用于标识需要复盘或二次确认的高风险配置、封禁与审计事项。</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="18">
      <el-col :xs="24" :xl="16">
        <section class="security-panel filter-panel">
          <div class="section-header">
            <div>
              <h3>日志筛选</h3>
              <p>支持按模块、结果和关键字快速定位审计记录，便于统一追踪关键操作过程。</p>
            </div>
          </div>

          <el-form :inline="true" :model="filterForm" class="filter-form">
            <el-form-item label="模块">
              <el-select v-model="filterForm.module" clearable placeholder="全部模块" style="width: 180px">
                <el-option label="处置申请" value="处置申请" />
                <el-option label="规则管理" value="规则管理" />
                <el-option label="用户管理" value="用户管理" />
                <el-option label="个人中心" value="个人中心" />
              </el-select>
            </el-form-item>

            <el-form-item label="结果">
              <el-select v-model="filterForm.result" clearable placeholder="全部结果" style="width: 180px">
                <el-option label="待审批" value="待审批" />
                <el-option label="已通过" value="已通过" />
                <el-option label="已驳回" value="已驳回" />
                <el-option label="已封禁" value="已封禁" />
                <el-option label="待复核" value="待复核" />
                <el-option label="已归档" value="已归档" />
              </el-select>
            </el-form-item>

            <el-form-item label="关键字">
              <el-input
                v-model="filterForm.keyword"
                clearable
                placeholder="输入操作人 / 目标 / 说明"
                style="width: 280px"
              />
            </el-form-item>
          </el-form>
        </section>

        <section class="security-panel table-panel">
          <div class="section-header">
            <div>
              <h3>审计记录</h3>
              <p>表格集中呈现“谁在什么时间对什么对象执行了什么动作以及结果如何”，便于统一核查关键操作留痕。</p>
            </div>
            <div class="table-header-tip">当前命中 {{ filteredAuditRecords.length }} 条记录</div>
          </div>

          <el-table v-loading="loading" :data="filteredAuditRecords" empty-text="当前没有匹配的审计记录">
            <el-table-column prop="audit_id" label="日志编号" min-width="160" />

            <el-table-column label="模块" min-width="120">
              <template #default="{ row }">
                <el-tag :type="moduleTagType(row.module)" effect="dark">
                  {{ row.module }}
                </el-tag>
              </template>
            </el-table-column>

            <el-table-column prop="action" label="操作动作" min-width="140" />

            <el-table-column label="操作人" min-width="140">
              <template #default="{ row }">
                <div class="operator-cell">
                  <div>{{ row.operator }}</div>
                  <el-tag size="small" :type="roleTagType(row.operator_role)" effect="plain">
                    {{ row.operator_role }}
                  </el-tag>
                </div>
              </template>
            </el-table-column>

            <el-table-column prop="target" label="操作对象" min-width="220" show-overflow-tooltip />

            <el-table-column label="处理结果" min-width="110">
              <template #default="{ row }">
                <el-tag :type="resultTagType(row.result)" effect="plain">
                  {{ row.result }}
                </el-tag>
              </template>
            </el-table-column>

            <el-table-column label="风险级别" min-width="100">
              <template #default="{ row }">
                <el-tag :type="riskTagType(row.risk_level)" effect="dark">
                  {{ row.risk_level }}
                </el-tag>
              </template>
            </el-table-column>

            <el-table-column prop="operated_at" label="操作时间" min-width="170" />

            <el-table-column label="操作" min-width="120" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="handleOpenDetail(row)">查看详情</el-button>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </el-col>

      <el-col :xs="24" :xl="8">
        <section class="security-panel side-panel">
          <div class="section-header">
            <div>
              <h3>职责边界说明</h3>
              <p>这里明确管理员与普通用户的差异在于高风险留痕与审批治理，而不是核心业务访问权。</p>
            </div>
          </div>

          <div class="tip-list">
            <div class="tip-item">
              <div class="tip-item__title">普通用户仍负责一线研判</div>
              <div class="tip-item__desc">值班分析员可查看工作台、检测结果、告警中心、图谱分析，并发起处置申请。</div>
            </div>
            <div class="tip-item">
              <div class="tip-item__title">管理员负责完整留痕追溯</div>
              <div class="tip-item__desc">只有管理员可查看规则发布、账号治理、审批动作与完整审计日志等高风险记录。</div>
            </div>
            <div class="tip-item">
              <div class="tip-item__title">审计日志支撑完整留痕追踪</div>
              <div class="tip-item__desc">通过时间、对象、结果与风险级别，支撑关键操作满足可审计、可复盘的管理要求。</div>
            </div>
          </div>
        </section>

        <section class="security-panel side-panel">
          <div class="section-header">
            <div>
              <h3>高风险动作提醒</h3>
              <p>优先呈现待复核或风险级别较高的治理动作，便于聚焦系统关键治理场景。</p>
            </div>
          </div>

          <div v-if="focusAuditItems.length > 0" class="focus-list">
            <div v-for="item in focusAuditItems" :key="item.audit_id" class="focus-card">
              <div class="focus-card__header">
                <div class="focus-card__title">{{ item.action }}</div>
                <el-tag size="small" :type="riskTagType(item.risk_level)" effect="dark">
                  {{ item.risk_level }}
                </el-tag>
              </div>
              <div class="focus-card__meta">模块：{{ item.module }}</div>
              <div class="focus-card__meta">对象：{{ item.target }}</div>
              <div class="focus-card__meta">结果：{{ item.result }}</div>
              <div class="focus-card__meta">时间：{{ item.operated_at }}</div>
            </div>
          </div>

          <el-empty v-else description="当前没有需要重点关注的高风险动作" />
        </section>
      </el-col>
    </el-row>

    <el-drawer v-model="detailDrawerVisible" title="审计详情" size="520px" destroy-on-close>
      <div v-if="currentDetail" class="detail-drawer">
        <div class="detail-grid">
          <div class="detail-card">
            <div class="detail-card__label">日志编号</div>
            <div class="detail-card__value">{{ currentDetail.audit_id }}</div>
          </div>
          <div class="detail-card">
            <div class="detail-card__label">模块</div>
            <div class="detail-card__value">{{ currentDetail.module }}</div>
          </div>
          <div class="detail-card">
            <div class="detail-card__label">操作人</div>
            <div class="detail-card__value">{{ currentDetail.operator }}</div>
          </div>
          <div class="detail-card">
            <div class="detail-card__label">风险级别</div>
            <div class="detail-card__value">{{ currentDetail.risk_level }}</div>
          </div>
        </div>

        <div class="detail-block">
          <div class="detail-block__title">操作对象</div>
          <div class="detail-block__content">{{ currentDetail.target }}</div>
        </div>

        <div class="detail-block">
          <div class="detail-block__title">处理结果</div>
          <div class="detail-block__content">{{ currentDetail.result }}</div>
        </div>

        <div class="detail-block">
          <div class="detail-block__title">审计说明</div>
          <div class="detail-block__content">{{ currentDetail.detail }}</div>
        </div>

        <div class="detail-block">
          <div class="detail-block__title">操作时间</div>
          <div class="detail-block__content">{{ currentDetail.operated_at }}</div>
        </div>
      </div>

      <el-empty v-else description="暂无审计详情" />
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { fetchAuditLogDetail, fetchAuditLogs } from "@/api/audit";
import { PERMISSION_KEYS, getCurrentUser, getRoleHomePath, getRoleLabel, hasPermission } from "@/utils/auth";

const router = useRouter();

const currentUser = ref(null);
const loading = ref(false);
const detailDrawerVisible = ref(false);
const auditRecords = ref([]);
const currentDetail = ref(null);

const filterForm = reactive({
  module: "",
  result: "",
  keyword: ""
});

const currentRoleLabel = computed(() => {
  return currentUser.value ? getRoleLabel(currentUser.value.role) : "未登录";
});

const canViewAudit = computed(() => {
  return hasPermission(currentUser.value, PERMISSION_KEYS.AUDIT_VIEW);
});

const adminActionCount = computed(() => {
  return auditRecords.value.filter((item) => item.operator_role === "管理员").length;
});

const highRiskCount = computed(() => {
  return auditRecords.value.filter((item) => item.risk_level === "高").length;
});

const filteredAuditRecords = computed(() => {
  const keyword = String(filterForm.keyword || "").trim().toLowerCase();

  return auditRecords.value.filter((item) => {
    if (filterForm.module && item.module !== filterForm.module) {
      return false;
    }

    if (filterForm.result && item.result !== filterForm.result) {
      return false;
    }

    if (!keyword) {
      return true;
    }

    const haystack = [item.action, item.operator, item.target, item.detail]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return haystack.includes(keyword);
  });
});

const focusAuditItems = computed(() => {
  return auditRecords.value
    .filter(
      (item) =>
        item.risk_level === "高" ||
        item.result === "待审批" ||
        item.action === "审批处置申请" ||
        item.action === "联动封禁处置" ||
        item.result === "已封禁"
    )
    .slice(0, 4);
});

async function loadPageData() {
  currentUser.value = getCurrentUser();

  if (!canViewAudit.value) {
    auditRecords.value = [];
    currentDetail.value = null;
    return;
  }

  loading.value = true;

  try {
    const response = await fetchAuditLogs();
    auditRecords.value = response.data?.items || [];
    currentDetail.value = auditRecords.value[0] || null;
  } finally {
    loading.value = false;
  }
}

function moduleTagType(module) {
  if (module === "规则管理") {
    return "warning";
  }

  if (module === "用户管理") {
    return "primary";
  }

  if (module === "个人中心") {
    return "success";
  }

  return "danger";
}

function roleTagType(role) {
  return role === "管理员" ? "danger" : "primary";
}

function resultTagType(result) {
  if (["已通过", "已归档"].includes(result)) {
    return "success";
  }

  if (result === "已封禁") {
    return "danger";
  }

  if (result === "已驳回") {
    return "danger";
  }

  if (["待审批", "待复核"].includes(result)) {
    return "warning";
  }

  return "info";
}

function riskTagType(riskLevel) {
  if (riskLevel === "高") {
    return "danger";
  }

  if (riskLevel === "中") {
    return "warning";
  }

  return "info";
}

async function handleOpenDetail(row) {
  const response = await fetchAuditLogDetail(row.audit_id);
  currentDetail.value = response.data || null;
  detailDrawerVisible.value = true;
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
.audit-log-page {
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
  color: var(--text-primary);
}

.summary-card__value--warning {
  color: var(--text-primary);
}

.summary-card__value--danger {
  color: var(--text-primary);
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

.operator-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-start;
}

.tip-list,
.focus-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tip-item,
.focus-card,
.detail-card,
.detail-block {
  padding: 14px;
  border-radius: 16px;
  background: var(--page-bg-accent);
  border: 1px solid var(--panel-border);
}

.tip-item__title,
.focus-card__title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.tip-item__desc,
.focus-card__meta,
.detail-card__label,
.detail-block__content {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
}

.focus-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.detail-drawer {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.detail-card__value {
  margin-top: 10px;
  font-size: 15px;
  line-height: 1.6;
  color: var(--text-primary);
  word-break: break-word;
}

.detail-block__title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

@media (max-width: 992px) {
  .page-banner,
  .section-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
