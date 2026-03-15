<template>
  <!--
    文件路径：frontend/src/views/BansView.vue
    作用说明：
    1. 展示封禁管理页面。
    2. 对接后端 GET /api/bans 接口。
    3. 展示封禁动作、关联告警、目标 IP 与执行状态等信息。
  -->
  <div class="bans-page app-page">
    <section class="security-panel page-banner">
      <div>
        <h1 class="page-title">封禁管理</h1>
        <p class="page-subtitle">
          当前页面用于展示系统联动产生的封禁与处置动作，便于审计演示“发现告警 - 触发处置 - 封禁目标”的闭环流程。
        </p>
      </div>

      <el-button type="primary" :loading="loading" @click="loadBans">
        刷新封禁数据
      </el-button>
    </section>

    <el-row :gutter="18" class="summary-grid">
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">当前页处置数</div>
          <div class="summary-card__value">{{ banItems.length }}</div>
          <div class="summary-card__hint">当前分页中返回的封禁或处置动作数量</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">成功执行数</div>
          <div class="summary-card__value summary-card__value--danger">{{ executedCount }}</div>
          <div class="summary-card__hint">状态为 SUCCESS / DONE / EXECUTED 的联动动作</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">可回滚动作数</div>
          <div class="summary-card__value summary-card__value--warning">{{ rollbackSupportedCount }}</div>
          <div class="summary-card__hint">具备回滚支持能力的处置动作数量</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">总记录数</div>
          <div class="summary-card__value summary-card__value--primary">{{ pagination.total }}</div>
          <div class="summary-card__hint">接口返回的封禁动作总数，用于分页展示</div>
        </div>
      </el-col>
    </el-row>

    <section class="security-panel filter-panel">
      <div class="section-header">
        <div>
          <h3>筛选条件</h3>
          <p>支持按封禁状态和目标 IP 进行联调查询。</p>
        </div>
      </div>

      <el-form :inline="true" :model="queryForm" class="filter-form">
        <el-form-item label="状态">
          <el-input
            v-model="queryForm.status"
            placeholder="请输入处置状态，如 SUCCESS"
            clearable
            style="width: 220px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>

        <el-form-item label="目标 IP">
          <el-input
            v-model="queryForm.target_ip"
            placeholder="请输入目标 IP 关键字"
            clearable
            style="width: 220px"
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
          <h3>封禁动作列表</h3>
          <p>展示封禁记录与关联告警，体现系统的自动处置与审计能力。</p>
        </div>

        <div class="table-header-tip">
          当前筛选：
          {{ activeFilterText }}
        </div>
      </div>

      <el-table :data="banItems" v-loading="loading" stripe>
        <el-table-column prop="action_id" label="动作编号" min-width="110" />
        <el-table-column prop="action_type" label="动作类型" min-width="130" />
        <el-table-column prop="target_type" label="目标类型" min-width="110" />

        <el-table-column label="执行状态" min-width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" effect="dark">
              {{ row.status || "-" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="ip_address" label="目标 IP" min-width="150" />
        <el-table-column label="IP 封禁标记" min-width="110">
          <template #default="{ row }">
            <el-tag :type="row.is_blocked ? 'danger' : 'info'" effect="plain">
              {{ row.is_blocked ? "已封禁" : "未标记" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="alert_name" label="关联告警" min-width="180" show-overflow-tooltip />
        <el-table-column prop="severity" label="告警等级" min-width="110" />
        <el-table-column prop="executor" label="执行主体" min-width="120" />
        <el-table-column prop="ticket_no" label="工单编号" min-width="140" show-overflow-tooltip />
        <el-table-column label="支持回滚" min-width="100">
          <template #default="{ row }">
            <el-tag :type="row.rollback_supported ? 'warning' : 'info'" effect="plain">
              {{ row.rollback_supported ? "支持" : "不支持" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="200" show-overflow-tooltip />
        <el-table-column prop="executed_at" label="执行时间" min-width="170" />
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
// 文件路径：frontend/src/views/BansView.vue
// 作用说明：
// 1. 通过 fetchBans 读取封禁管理分页接口。
// 2. 将接口 items 映射为封禁动作表格。
// 3. 用摘要卡片展示执行态势，便于演示自动封禁闭环。

import { computed, onMounted, reactive, ref } from "vue";

import { fetchBans } from "@/api/bans";

const loading = ref(false);
const banItems = ref([]);

const queryForm = reactive({
  status: "",
  target_ip: ""
});

const pagination = reactive({
  page: 1,
  size: 10,
  total: 0
});

const executedStatusSet = ["SUCCESS", "DONE", "EXECUTED", "BLOCKED"];

const executedCount = computed(() => {
  return banItems.value.filter((item) => executedStatusSet.includes(String(item.status || "").toUpperCase())).length;
});

const rollbackSupportedCount = computed(() => {
  return banItems.value.filter((item) => item.rollback_supported === true).length;
});

const activeFilterText = computed(() => {
  const segments = [];

  if (queryForm.status) {
    segments.push(`状态 ${queryForm.status}`);
  }

  if (queryForm.target_ip) {
    segments.push(`目标 IP ${queryForm.target_ip}`);
  }

  return segments.length > 0 ? segments.join(" / ") : "未设置筛选条件";
});

function statusTagType(status) {
  const normalizedStatus = String(status || "").toUpperCase();

  if (["SUCCESS", "DONE", "EXECUTED", "BLOCKED"].includes(normalizedStatus)) {
    return "danger";
  }

  if (["PENDING", "WAITING", "QUEUED"].includes(normalizedStatus)) {
    return "warning";
  }

  if (["ROLLED_BACK", "RESOLVED"].includes(normalizedStatus)) {
    return "success";
  }

  return "info";
}

async function loadBans() {
  loading.value = true;

  try {
    const response = await fetchBans({
      page: pagination.page,
      size: pagination.size,
      status: queryForm.status || undefined,
      target_ip: queryForm.target_ip || undefined
    });

    const data = response?.data || {};
    banItems.value = data.items || [];
    pagination.page = data.pagination?.page || 1;
    pagination.size = data.pagination?.size || 10;
    pagination.total = data.pagination?.total || 0;
  } finally {
    loading.value = false;
  }
}

function handleSearch() {
  pagination.page = 1;
  loadBans();
}

function handleReset() {
  queryForm.status = "";
  queryForm.target_ip = "";
  pagination.page = 1;
  pagination.size = 10;
  loadBans();
}

function handlePageChange(page) {
  pagination.page = page;
  loadBans();
}

function handleSizeChange(size) {
  pagination.size = size;
  pagination.page = 1;
  loadBans();
}

onMounted(() => {
  loadBans();
});
</script>

<style scoped>
.bans-page {
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
