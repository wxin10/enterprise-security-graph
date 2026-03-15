<template>
  <!--
    文件路径：frontend/src/views/BansView.vue
    作用说明：
    1. 展示封禁管理页面。
    2. 对接封禁列表与放行接口，形成“封禁 -> 放行 / 解封”的响应闭环。
    3. 明确区分历史动作、最近动作、当前封禁状态和放行审计信息。
  -->
  <div class="bans-page app-page">
    <section class="security-panel page-banner">
      <div>
        <h1 class="page-title">封禁管理</h1>
        <p class="page-subtitle">
          当前页面用于展示系统联动产生的封禁与恢复动作，便于审计演示“发现告警 - 触发封禁 - 人工放行 / 解封”的安全响应闭环。
        </p>
      </div>

      <el-button type="primary" :loading="loading" @click="loadBans">
        刷新封禁数据
      </el-button>
    </section>

    <el-row :gutter="18" class="summary-grid">
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">当前页记录数</div>
          <div class="summary-card__value">{{ banItems.length }}</div>
          <div class="summary-card__hint">当前分页中返回的封禁或放行记录数量</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">当前仍处封禁</div>
          <div class="summary-card__value summary-card__value--danger">{{ blockedCount }}</div>
          <div class="summary-card__hint">当前状态为 BLOCKED 的记录数量</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">已放行 / 已解封</div>
          <div class="summary-card__value summary-card__value--success">{{ releasedCount }}</div>
          <div class="summary-card__hint">当前状态为 RELEASED 的记录数量</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">可执行放行</div>
          <div class="summary-card__value summary-card__value--warning">{{ releasableCount }}</div>
          <div class="summary-card__hint">支持回滚且当前仍处封禁状态的记录数量</div>
        </div>
      </el-col>
    </el-row>

    <section class="security-panel filter-panel">
      <div class="section-header">
        <div>
          <h3>筛选条件</h3>
          <p>支持按执行状态、当前封禁状态和目标 IP 进行联调查询。</p>
        </div>
      </div>

      <el-form :inline="true" :model="queryForm" class="filter-form">
        <el-form-item label="状态">
          <el-input
            v-model="queryForm.status"
            placeholder="如 BLOCKED / RELEASED / SUCCESS"
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
          />
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
          <p>列表会同时展示历史封禁动作、最近动作、当前封禁状态以及放行审计信息。</p>
        </div>

        <div class="table-header-tip">
          当前筛选：{{ activeFilterText }}
        </div>
      </div>

      <el-table :data="banItems" v-loading="loading" stripe>
        <el-table-column prop="action_id" label="记录编号" min-width="110" />

        <el-table-column label="历史动作" min-width="120">
          <template #default="{ row }">
            <el-tag :type="actionTypeTagType(row.action_type)" effect="dark">
              {{ row.action_type || "-" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="最近动作" min-width="120">
          <template #default="{ row }">
            <el-tag :type="actionTypeTagType(row.latest_action_type)" effect="plain">
              {{ row.latest_action_type || "-" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="target_type" label="目标类型" min-width="100" />

        <el-table-column label="当前封禁状态" min-width="130">
          <template #default="{ row }">
            <el-tag :type="currentStatusTagType(row.current_ban_status)" effect="dark">
              {{ formatCurrentStatus(row.current_ban_status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="执行状态" min-width="120">
          <template #default="{ row }">
            <el-tag :type="executionStatusTagType(row.status)" effect="plain">
              {{ row.status || "-" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="ip_address" label="目标 IP" min-width="150" />

        <el-table-column label="图数据库状态" min-width="120">
          <template #default="{ row }">
            <el-tag :type="row.is_blocked ? 'danger' : 'success'" effect="plain">
              {{ row.is_blocked ? "Neo4j: 已封禁" : "Neo4j: 已放行" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="alert_name" label="关联告警" min-width="180" show-overflow-tooltip />
        <el-table-column prop="severity" label="告警等级" min-width="100" />
        <el-table-column prop="executor" label="封禁执行人" min-width="110" />
        <el-table-column prop="released_by" label="放行执行人" min-width="110" />
        <el-table-column prop="executed_at" label="封禁时间" min-width="170" />
        <el-table-column prop="released_at" label="放行时间" min-width="170" />
        <el-table-column prop="release_reason" label="放行原因" min-width="220" show-overflow-tooltip />
        <el-table-column prop="ticket_no" label="工单编号" min-width="140" show-overflow-tooltip />
        <el-table-column prop="remark" label="备注" min-width="200" show-overflow-tooltip />

        <el-table-column label="支持回滚" min-width="100">
          <template #default="{ row }">
            <el-tag :type="row.rollback_supported ? 'warning' : 'info'" effect="plain">
              {{ row.rollback_supported ? "支持" : "不支持" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.can_unban"
              type="danger"
              link
              :loading="isRowUnbanning(row.action_id)"
              @click="handleUnban(row)"
            >
              放行
            </el-button>
            <el-tag v-else-if="row.is_released" type="success" effect="plain">已放行</el-tag>
            <el-tag v-else type="info" effect="plain">不可放行</el-tag>
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
  </div>
</template>

<script setup>
// 文件路径：frontend/src/views/BansView.vue
// 作用说明：
// 1. 通过 fetchBans 读取封禁列表，并对接新增加的放行 / 解封接口。
// 2. 前端用当前封禁状态、最近动作和放行审计字段增强展示语义。
// 3. 点击“放行”时通过确认输入框填写原因，并在成功后立即刷新列表。
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { fetchBans, unbanBan } from "@/api/bans";

const loading = ref(false);
const banItems = ref([]);
const unbanLoadingMap = reactive({});

const queryForm = reactive({
  status: "",
  target_ip: ""
});

const pagination = reactive({
  page: 1,
  size: 10,
  total: 0
});

const blockedCount = computed(() => {
  return banItems.value.filter((item) => item.current_ban_status === "BLOCKED").length;
});

const releasedCount = computed(() => {
  return banItems.value.filter((item) => item.current_ban_status === "RELEASED").length;
});

const releasableCount = computed(() => {
  return banItems.value.filter((item) => item.can_unban === true).length;
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

function actionTypeTagType(actionType) {
  const normalizedActionType = String(actionType || "").toUpperCase();

  if (normalizedActionType === "UNBLOCK_IP") {
    return "success";
  }

  if (normalizedActionType === "BLOCK_IP") {
    return "danger";
  }

  return "info";
}

function executionStatusTagType(status) {
  const normalizedStatus = String(status || "").toUpperCase();

  if (["SUCCESS", "DONE", "EXECUTED", "BLOCKED"].includes(normalizedStatus)) {
    return "danger";
  }

  if (["RELEASED", "UNBLOCKED", "ROLLED_BACK", "RESOLVED"].includes(normalizedStatus)) {
    return "success";
  }

  if (["PENDING", "WAITING", "QUEUED"].includes(normalizedStatus)) {
    return "warning";
  }

  if (normalizedStatus === "FAILED") {
    return "danger";
  }

  return "info";
}

function currentStatusTagType(status) {
  const normalizedStatus = String(status || "").toUpperCase();

  if (normalizedStatus === "BLOCKED") {
    return "danger";
  }

  if (normalizedStatus === "RELEASED") {
    return "success";
  }

  if (normalizedStatus === "FAILED") {
    return "danger";
  }

  if (normalizedStatus === "PENDING") {
    return "warning";
  }

  return "info";
}

function formatCurrentStatus(status) {
  const normalizedStatus = String(status || "").toUpperCase();

  if (normalizedStatus === "BLOCKED") {
    return "已封禁";
  }

  if (normalizedStatus === "RELEASED") {
    return "已放行";
  }

  if (normalizedStatus === "FAILED") {
    return "执行失败";
  }

  if (normalizedStatus === "PENDING") {
    return "待执行";
  }

  return normalizedStatus || "-";
}

function isRowUnbanning(actionId) {
  return Boolean(unbanLoadingMap[actionId]);
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

async function handleUnban(row) {
  if (!row?.can_unban) {
    return;
  }

  try {
    const promptResult = await ElMessageBox.prompt(
      `请填写对记录 ${row.action_id} 的放行原因。`,
      "确认放行 / 解封",
      {
        confirmButtonText: "确认放行",
        cancelButtonText: "取消",
        inputType: "textarea",
        inputValue: "人工复核后确认放行",
        inputPlaceholder: "请输入放行原因"
      }
    );

    unbanLoadingMap[row.action_id] = true;
    const response = await unbanBan(row.action_id, {
      release_reason: promptResult.value || "人工复核后确认放行",
      released_by: "security_console"
    });

    ElMessage.success(response?.message || "放行成功");
    await loadBans()
  } catch (error) {
    if (error === "cancel" || error === "close" || error?.action === "cancel" || error?.action === "close") {
      return;
    }
  } finally {
    unbanLoadingMap[row.action_id] = false;
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

.summary-card__value--success {
  color: #5dd598;
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
