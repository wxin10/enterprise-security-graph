<template>
  <!--
    文件路径：frontend/src/views/AlertsView.vue
    作用说明：
    1. 展示告警管理页面。
    2. 对接后端 GET /api/alerts 接口，提供筛选、分页和摘要展示。
    3. 新增“查看攻击链”入口，并通过抽屉展示面向安全语义的攻击链图谱。
  -->
  <div class="alerts-page app-page">
    <section class="security-panel page-banner">
      <div>
        <h1 class="page-title">告警中心</h1>
        <p class="page-subtitle">
          统一展示安全告警记录与处置态势，支持按状态、严重等级和关键字检索，并可查看单条告警关联的攻击链信息。
        </p>
      </div>

      <el-button type="primary" :loading="loading" @click="loadAlerts">
        刷新告警列表
      </el-button>
    </section>

    <el-row :gutter="18" class="summary-grid">
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">当前页告警数</div>
          <div class="summary-card__value">{{ alertItems.length }}</div>
          <div class="summary-card__hint">当前分页返回的告警记录数量</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">高风险告警数</div>
          <div class="summary-card__value summary-card__value--danger">{{ criticalAlertCount }}</div>
          <div class="summary-card__hint">当前页中 HIGH 与 CRITICAL 级别的告警数量</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">联动处置数</div>
          <div class="summary-card__value summary-card__value--warning">{{ blockedLinkedCount }}</div>
          <div class="summary-card__hint">当前页中已触发封禁或处置动作的告警数量</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">告警总量</div>
          <div class="summary-card__value summary-card__value--primary">{{ pagination.total }}</div>
          <div class="summary-card__hint">接口返回的告警总量，用于分页展示</div>
        </div>
      </el-col>
    </el-row>

    <section class="security-panel filter-panel">
      <div class="section-header">
        <div>
          <h3>筛选条件</h3>
          <p>支持按告警状态、严重等级和关键字快速筛选当前告警记录。</p>
        </div>
      </div>

      <el-form :inline="true" :model="queryForm" class="filter-form">
        <el-form-item label="状态">
          <el-select v-model="queryForm.status" placeholder="全部状态" clearable style="width: 150px">
            <el-option label="NEW" value="NEW" />
            <el-option label="CONFIRMED" value="CONFIRMED" />
            <el-option label="BLOCKED" value="BLOCKED" />
            <el-option label="RESOLVED" value="RESOLVED" />
          </el-select>
        </el-form-item>

        <el-form-item label="等级">
          <el-select v-model="queryForm.severity" placeholder="全部等级" clearable style="width: 150px">
            <el-option label="LOW" value="LOW" />
            <el-option label="MEDIUM" value="MEDIUM" />
            <el-option label="HIGH" value="HIGH" />
            <el-option label="CRITICAL" value="CRITICAL" />
          </el-select>
        </el-form-item>

        <el-form-item label="关键字">
          <el-input
            v-model="queryForm.keyword"
            placeholder="请输入告警名称或描述关键字"
            clearable
            style="width: 260px"
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </section>

    <section class="security-panel table-panel">
      <div class="section-header">
        <div>
          <h3>告警列表</h3>
          <p>展示符合筛选条件的告警记录，并提供对应攻击链查看入口。</p>
        </div>

        <div class="table-header-tip">
          当前筛选：
          {{ activeFilterText }}
        </div>
      </div>

      <el-table :data="alertItems" v-loading="loading" stripe>
        <el-table-column prop="alert_id" label="告警编号" min-width="110" />
        <el-table-column prop="alert_name" label="告警名称" min-width="180" show-overflow-tooltip />

        <el-table-column label="严重等级" min-width="110">
          <template #default="{ row }">
            <el-tag :type="severityTagType(row.severity)" effect="plain">
              {{ row.severity || "-" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="状态" min-width="110">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" effect="plain">
              {{ row.status || "-" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="score" label="风险得分" min-width="90" />

        <el-table-column label="行为类型" min-width="140">
          <template #default="{ row }">
            <el-tag v-if="row.behavior_type" type="warning" effect="plain">
              {{ row.behavior_type }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column prop="event_count" label="证据事件数" min-width="100" />

        <el-table-column label="可封禁" min-width="90">
          <template #default="{ row }">
            <el-tag :type="row.can_block ? 'danger' : 'info'" effect="plain">
              {{ row.can_block ? "是" : "否" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="事件类型" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ joinArray(row.event_types) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="命中规则" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ joinArray(row.rule_names) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="处置动作" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ joinArray(row.action_types) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="description" label="告警描述" min-width="220" show-overflow-tooltip />
        <el-table-column prop="suggestion" label="处置建议" min-width="220" show-overflow-tooltip />
        <el-table-column prop="last_seen" label="最近时间" min-width="170" />

        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleOpenAttackChain(row)">
              查看攻击链
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-bar">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next"
          :current-page="pagination.page"
          :page-size="pagination.size"
          :page-sizes="[10, 20, 50]"
          :total="pagination.total"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </section>

    <el-drawer
      v-model="attackChainVisible"
      size="72%"
      :destroy-on-close="false"
      :with-header="true"
      class="attack-chain-drawer"
    >
      <template #header>
        <div class="drawer-header">
          <div>
            <div class="drawer-title">攻击链图谱</div>
            <div class="drawer-subtitle">
              {{ selectedAlert?.alert_name || "当前告警" }} · {{ selectedAlert?.alert_id || "-" }}
            </div>
          </div>
        </div>
      </template>

      <div class="attack-chain-panel">
        <div class="attack-chain-summary-grid">
          <div class="security-panel attack-chain-summary-card" v-for="item in attackChainSummaryCards" :key="item.key">
            <div class="attack-chain-summary-card__label">{{ item.label }}</div>
            <div class="attack-chain-summary-card__value" :class="item.className">{{ item.value }}</div>
          </div>
        </div>

        <div class="security-panel attack-chain-hint">
          <div class="attack-chain-hint__title">链路摘要</div>
          <div class="attack-chain-hint__text">{{ attackChainData.summary.message || defaultAttackChainMessage }}</div>
        </div>

        <AttackChainGraph
          :graph-data="attackChainData"
          :loading="attackChainLoading"
          :empty-text="attackChainData.summary.message || defaultAttackChainMessage"
        />
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
// 文件路径：frontend/src/views/AlertsView.vue
// 作用说明：
// 1. 通过 fetchAlerts 对接后端告警分页接口。
// 2. 保留原有筛选、分页和摘要卡片能力。
// 3. 新增“查看攻击链”抽屉，调用攻击链接口并以 ECharts graph 展示真实攻击事件关系。
import { computed, onMounted, reactive, ref } from "vue";

import AttackChainGraph from "@/components/AttackChainGraph.vue";
import { fetchAlertAttackChain, fetchAlerts } from "@/api/alerts";

const loading = ref(false);
const attackChainLoading = ref(false);
const attackChainVisible = ref(false);
const alertItems = ref([]);
const selectedAlert = ref(null);

const defaultAttackChainMessage = "当前告警缺少足够的关联证据，暂无法完整展示攻击链。";

const queryForm = reactive({
  status: "",
  severity: "",
  keyword: ""
});

const pagination = reactive({
  page: 1,
  size: 10,
  total: 0
});

const attackChainData = reactive({
  nodes: [],
  links: [],
  summary: {
    source_ip: "-",
    attack_type: "-",
    target_asset: "-",
    matched_rule: "-",
    alert_level: "-",
    ban_status: "-",
    message: defaultAttackChainMessage
  }
});

const criticalAlertCount = computed(() => {
  return alertItems.value.filter((item) => ["HIGH", "CRITICAL"].includes(item.severity)).length;
});

const blockedLinkedCount = computed(() => {
  return alertItems.value.filter((item) => Array.isArray(item.action_types) && item.action_types.length > 0).length;
});

const activeFilterText = computed(() => {
  const segments = [];

  if (queryForm.status) {
    segments.push(`状态：${queryForm.status}`);
  }

  if (queryForm.severity) {
    segments.push(`等级：${queryForm.severity}`);
  }

  if (queryForm.keyword) {
    segments.push(`关键字：${queryForm.keyword}`);
  }

  return segments.length > 0 ? segments.join(" / ") : "未设置筛选条件";
});

const attackChainSummaryCards = computed(() => {
  const summary = attackChainData.summary || {};

  return [
    {
      key: "source_ip",
      label: "攻击源 IP",
      value: summary.source_ip || "-",
      className: "attack-chain-summary-card__value--primary"
    },
    {
      key: "attack_type",
      label: "攻击类型",
      value: summary.attack_type || "-",
      className: "attack-chain-summary-card__value--warning"
    },
    {
      key: "target_asset",
      label: "目标资产",
      value: summary.target_asset || "-",
      className: ""
    },
    {
      key: "matched_rule",
      label: "命中规则",
      value: summary.matched_rule || "-",
      className: ""
    },
    {
      key: "alert_level",
      label: "告警等级",
      value: summary.alert_level || "-",
      className: "attack-chain-summary-card__value--danger"
    },
    {
      key: "ban_status",
      label: "封禁状态",
      value: summary.ban_status || "-",
      className: "attack-chain-summary-card__value--success"
    }
  ];
});

function resetAttackChainData() {
  attackChainData.nodes = [];
  attackChainData.links = [];
  attackChainData.summary = {
    source_ip: "-",
    attack_type: "-",
    target_asset: "-",
    matched_rule: "-",
    alert_level: selectedAlert.value?.severity || "-",
    ban_status: "-",
    message: defaultAttackChainMessage
  };
}

function joinArray(value) {
  if (!Array.isArray(value) || value.length === 0) {
    return "-";
  }

  return value.filter(Boolean).join(" / ") || "-";
}

function severityTagType(severity) {
  if (severity === "CRITICAL" || severity === "HIGH") {
    return "danger";
  }

  if (severity === "MEDIUM") {
    return "warning";
  }

  if (severity === "LOW") {
    return "success";
  }

  return "info";
}

function statusTagType(status) {
  if (status === "BLOCKED") {
    return "danger";
  }

  if (status === "CONFIRMED") {
    return "warning";
  }

  if (status === "RESOLVED") {
    return "success";
  }

  return "info";
}

async function loadAlerts() {
  loading.value = true;

  try {
    const response = await fetchAlerts({
      page: pagination.page,
      size: pagination.size,
      status: queryForm.status || undefined,
      severity: queryForm.severity || undefined,
      keyword: queryForm.keyword || undefined
    });

    const data = response?.data || {};
    alertItems.value = data.items || [];
    pagination.page = data.pagination?.page || 1;
    pagination.size = data.pagination?.size || 10;
    pagination.total = data.pagination?.total || 0;
  } finally {
    loading.value = false;
  }
}

async function handleOpenAttackChain(row) {
  selectedAlert.value = row;
  attackChainVisible.value = true;
  attackChainLoading.value = true;
  resetAttackChainData();

  try {
    const response = await fetchAlertAttackChain(row.alert_id);
    const data = response?.data || {};

    attackChainData.nodes = data.nodes || [];
    attackChainData.links = data.links || [];
    attackChainData.summary = {
      ...attackChainData.summary,
      ...(data.summary || {})
    };
  } catch (error) {
    attackChainData.summary = {
      ...attackChainData.summary,
      alert_level: row?.severity || "-",
      message: "当前告警暂时无法生成完整攻击链，已保留基础告警摘要，请稍后重试或核查关联证据数据。"
    };
  } finally {
    attackChainLoading.value = false;
  }
}

function handleSearch() {
  pagination.page = 1;
  loadAlerts();
}

function handleReset() {
  queryForm.status = "";
  queryForm.severity = "";
  queryForm.keyword = "";
  pagination.page = 1;
  pagination.size = 10;
  loadAlerts();
}

function handlePageChange(page) {
  pagination.page = page;
  loadAlerts();
}

function handleSizeChange(size) {
  pagination.size = size;
  pagination.page = 1;
  loadAlerts();
}

onMounted(() => {
  loadAlerts();
});
</script>

<style scoped>
.alerts-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-banner,
.filter-panel,
.table-panel,
.summary-card {
  padding: 20px;
}

.page-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
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
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary);
}

.summary-card__value--danger {
  color: #ff6f7d;
}

.summary-card__value--warning {
  color: #ffbf5a;
}

.summary-card__value--primary {
  color: #67a8ff;
}

.summary-card__hint {
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.summary-card,
.attack-chain-summary-card,
.attack-chain-hint {
  border: 1px solid var(--panel-border);
  background: var(--page-bg-accent);
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

.table-header-tip {
  color: var(--text-secondary);
  font-size: 13px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 0;
}

.pagination-bar {
  display: flex;
  justify-content: flex-end;
  margin-top: 18px;
}

.drawer-header {
  display: flex;
  align-items: center;
}

.drawer-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.drawer-subtitle {
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 13px;
}

.attack-chain-panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.attack-chain-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.attack-chain-summary-card {
  padding: 16px;
}

.attack-chain-summary-card__label {
  font-size: 13px;
  color: var(--text-secondary);
}

.attack-chain-summary-card__value {
  margin-top: 10px;
  font-size: 18px;
  line-height: 1.6;
  color: var(--text-primary);
  font-weight: 700;
  word-break: break-word;
}

.attack-chain-summary-card__value--primary {
  color: #67a8ff;
}

.attack-chain-summary-card__value--warning {
  color: #ffbf5a;
}

.attack-chain-summary-card__value--danger {
  color: #ff7285;
}

.attack-chain-summary-card__value--success {
  color: #5dd598;
}

.attack-chain-hint {
  padding: 16px 18px;
}

.attack-chain-hint__title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.attack-chain-hint__text {
  margin-top: 8px;
  color: var(--text-secondary);
  line-height: 1.8;
  font-size: 13px;
}

@media (max-width: 1200px) {
  .attack-chain-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 992px) {
  .page-banner,
  .section-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .attack-chain-summary-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 960px) {
  .pagination-bar {
    justify-content: center;
    overflow-x: auto;
  }
}
</style>
