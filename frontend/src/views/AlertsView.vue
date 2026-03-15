<template>
  <!--
    文件路径：frontend/src/views/AlertsView.vue
    作用说明：
    1. 展示告警管理页面。
    2. 对接后端 GET /api/alerts 接口。
    3. 提供基础筛选、分页和当前页摘要信息，便于联调和论文演示。
  -->
  <div class="alerts-page app-page">
    <section class="security-panel page-banner">
      <div>
        <h1 class="page-title">告警管理</h1>
        <p class="page-subtitle">
          当前页面用于展示图谱分析后的安全告警列表，可按状态、严重等级和关键字进行查询，并结合联动处置结果进行研判。
        </p>
      </div>

      <el-button type="primary" :loading="loading" @click="loadAlerts">
        刷新告警数据
      </el-button>
    </section>

    <el-row :gutter="18" class="summary-grid">
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">当前页告警数</div>
          <div class="summary-card__value">{{ alertItems.length }}</div>
          <div class="summary-card__hint">当前分页中返回的告警记录数量</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">高危告警数</div>
          <div class="summary-card__value summary-card__value--danger">{{ criticalAlertCount }}</div>
          <div class="summary-card__hint">当前页中 HIGH / CRITICAL 级别的告警</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">联动处置数</div>
          <div class="summary-card__value summary-card__value--warning">{{ blockedLinkedCount }}</div>
          <div class="summary-card__hint">当前页中已出现封禁或处置动作的告警</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">总记录数</div>
          <div class="summary-card__value summary-card__value--primary">{{ pagination.total }}</div>
          <div class="summary-card__hint">接口返回的告警总量，用于分页展示</div>
        </div>
      </el-col>
    </el-row>

    <section class="security-panel filter-panel">
      <div class="section-header">
        <div>
          <h3>筛选条件</h3>
          <p>支持按告警状态、严重等级和关键字进行基础联调测试。</p>
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
          <p>表格字段对齐后端接口返回的 items 结构，便于后续继续扩展告警详情页。</p>
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
            <el-tag :type="severityTagType(row.severity)" effect="dark">
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
  </div>
</template>

<script setup>
// 文件路径：frontend/src/views/AlertsView.vue
// 作用说明：
// 1. 通过 fetchAlerts 对接后端告警分页接口。
// 2. 将接口中的 items 和 pagination 结构映射为表格与分页组件。
// 3. 在不增加复杂交互的前提下，补充摘要卡片，提升页面信息密度。

import { computed, onMounted, reactive, ref } from "vue";

import { fetchAlerts } from "@/api/alerts";

const loading = ref(false);
const alertItems = ref([]);

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

const criticalAlertCount = computed(() => {
  return alertItems.value.filter((item) => ["HIGH", "CRITICAL"].includes(item.severity)).length;
});

const blockedLinkedCount = computed(() => {
  return alertItems.value.filter((item) => Array.isArray(item.action_types) && item.action_types.length > 0).length;
});

const activeFilterText = computed(() => {
  const segments = [];

  if (queryForm.status) {
    segments.push(`状态 ${queryForm.status}`);
  }

  if (queryForm.severity) {
    segments.push(`等级 ${queryForm.severity}`);
  }

  if (queryForm.keyword) {
    segments.push(`关键字 ${queryForm.keyword}`);
  }

  return segments.length > 0 ? segments.join(" / ") : "未设置筛选条件";
});

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
  color: #8aa3c8;
}

.summary-card__value {
  margin-top: 12px;
  font-size: 32px;
  font-weight: 700;
  color: #eef5ff;
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
  color: #7f98be;
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
  color: #ecf4ff;
}

.section-header p {
  margin: 8px 0 0;
  color: #8aa3c8;
  font-size: 13px;
  line-height: 1.7;
}

.table-header-tip {
  color: #8fa7ca;
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

@media (max-width: 992px) {
  .page-banner,
  .section-header {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 960px) {
  .pagination-bar {
    justify-content: center;
    overflow-x: auto;
  }
}
</style>
