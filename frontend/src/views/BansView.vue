<template>
  <!--
    文件路径：frontend/src/views/BansView.vue
    作用说明：
    1. 在封禁管理页面中呈现当前状态、历史动作、执行结果和规则校验结果。
    2. 支持已封禁 -> 放行、已放行 -> 重新封禁，以及对当前状态执行规则校验。
    3. 通过业务状态与主机执行状态的联动信息，帮助用户核查封禁处置结果。
  -->
  <div class="bans-page app-page">
    <section class="security-panel page-banner">
      <div>
        <h1 class="page-title">封禁管理</h1>
        <p class="page-subtitle">
          集中呈现攻击源 IP 的主机级封禁结果、最近动作与执行状态，支持放行与重新封禁双向切换。
        </p>
      </div>

      <div class="page-banner__actions">
        <el-tag :type="executionModeTagType" effect="dark" size="large">
          当前执行模式：{{ formatEnforcementModeDisplay(enforcementProfile.mode) }}
        </el-tag>

        <el-button type="primary" :loading="loading" @click="loadBans">
          刷新封禁数据
        </el-button>
      </div>
    </section>

    <el-row :gutter="18" class="summary-grid">
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">总记录数</div>
          <div class="summary-card__value summary-card__value--primary">{{ pagination.total }}</div>
          <div class="summary-card__hint">统计当前查询条件下的封禁目标数量</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">当前已封禁</div>
          <div class="summary-card__value summary-card__value--danger">{{ blockedCount }}</div>
          <div class="summary-card__hint">当前状态为 BLOCKED 的记录，可继续执行放行或封禁校验</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">当前已放行</div>
          <div class="summary-card__value summary-card__value--success">{{ releasedCount }}</div>
          <div class="summary-card__hint">当前状态为 RELEASED 的记录，可继续执行重新封禁或放行校验</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">校验通过数</div>
          <div class="summary-card__value summary-card__value--warning">{{ verifiedCount }}</div>
          <div class="summary-card__hint">当前页已完成规则校验并通过的记录数量</div>
        </div>
      </el-col>
    </el-row>

    <section class="security-panel filter-panel">
      <div class="section-header">
        <div>
          <h3>筛选条件</h3>
          <p>支持按当前状态和目标 IP 快速定位待复核的处置对象。</p>
        </div>
      </div>

      <el-form :inline="true" :model="queryForm" class="filter-form">
        <el-form-item label="状态">
          <el-select v-model="queryForm.status" clearable placeholder="全部状态" style="width: 180px">
            <el-option label="BLOCKED" value="BLOCKED" />
            <el-option label="RELEASED" value="RELEASED" />
          </el-select>
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
          <h3>当前状态列表</h3>
          <p>列表集中呈现当前状态、最近动作、目标 IP 以及关键执行结果。</p>
        </div>

        <div class="table-header-tip">当前筛选：{{ activeFilterText }}</div>
      </div>

      <el-table :data="banItems" v-loading="loading" stripe>
        <el-table-column prop="action_id" label="记录编号" min-width="120" />
        <el-table-column prop="ip_address" label="目标 IP" min-width="140" />

        <el-table-column label="当前状态" min-width="110">
          <template #default="{ row }">
            <el-tag :type="currentStatusTagType(row.current_ban_status)" effect="dark">
              {{ formatCurrentStatus(row.current_ban_status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="原始动作" min-width="110">
          <template #default="{ row }">
            <el-tag :type="actionTypeTagType(row.action_type)" effect="plain">
              {{ formatActionLabel(row.action_type) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="最近动作" min-width="120">
          <template #default="{ row }">
            <el-tag :type="actionTypeTagType(row.latest_action_type)" effect="dark">
              {{ formatActionLabel(row.latest_action_type) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="latest_action_at" label="最近操作时间" min-width="170" />

        <el-table-column label="封禁来源" min-width="100">
          <template #default="{ row }">
            <el-tag :type="blockSourceTagType(row.block_source)" effect="plain">
              {{ formatBlockSource(row.block_source) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="攻击类型" min-width="140">
          <template #default="{ row }">
            <el-tag v-if="row.behavior_type" type="warning" effect="plain">
              {{ row.behavior_type }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column prop="risk_score" label="攻击风险分" min-width="100" />

        <el-table-column prop="block_reason" label="封禁原因" min-width="220" show-overflow-tooltip />

        <el-table-column label="执行模式" min-width="120">
          <template #default="{ row }">
            <el-tag :type="row.enforcement_mode === 'REAL' ? 'danger' : 'info'" effect="plain">
              {{ formatEnforcementModeDisplay(row.enforcement_mode) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="enforcement_backend" label="执行后端" min-width="150">
          <template #default="{ row }">
            <span>{{ formatEnforcementBackend(row.enforcement_backend) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="规则下发结果" min-width="140">
          <template #default="{ row }">
            <el-tag :type="enforcementStatusTagType(row.enforcement_status)" effect="dark">
              {{ formatEnforcementStatus(row.enforcement_status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="执行成功" min-width="100">
          <template #default="{ row }">
            <span v-if="row.enforcement_success === null || row.enforcement_success === undefined">-</span>
            <el-tag v-else :type="row.enforcement_success ? 'success' : 'info'" effect="plain">
              {{ row.enforcement_success ? "成功" : "未成功" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="校验状态" min-width="120">
          <template #default="{ row }">
            <el-tag :type="verificationStatusTagType(row.verification_status)" effect="plain">
              {{ formatVerificationStatus(row.verification_status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="真实阻断" min-width="100">
          <template #default="{ row }">
            <span v-if="row.truly_blocked === null || row.truly_blocked === undefined">-</span>
            <el-tag v-else :type="row.truly_blocked ? 'danger' : 'info'" effect="dark">
              {{ row.truly_blocked ? "已阻断" : "未阻断" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="verified_at" label="校验时间" min-width="170" />
        <el-table-column prop="enforcement_rule_name" label="规则名" min-width="240" show-overflow-tooltip />
        <el-table-column prop="verification_message" label="校验说明" min-width="240" show-overflow-tooltip />

        <el-table-column label="历史动作摘要" min-width="240">
          <template #default="{ row }">
            <div class="history-cell">
              <div class="history-chip-list">
                <el-tag
                  v-for="item in row.history_actions_brief"
                  :key="`${row.action_id}-${item.sequence}`"
                  :type="actionTypeTagType(item.action_type)"
                  effect="plain"
                  size="small"
                >
                  {{ formatActionLabel(item.action_type) }}
                </el-tag>
              </div>
              <div class="history-summary-text">{{ row.history_summary || "-" }}</div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="次数统计" min-width="120">
          <template #default="{ row }">
            <div class="count-stack">
              <div>封禁 {{ row.block_count || 0 }}</div>
              <div>放行 {{ row.release_count || 0 }}</div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="状态时间" min-width="170">
          <template #default="{ row }">
            <div class="time-stack">
              <div>封禁：{{ row.blocked_at || "-" }}</div>
              <div>放行：{{ row.released_at || "-" }}</div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="Neo4j 当前状态" min-width="130">
          <template #default="{ row }">
            <el-tag :type="row.is_blocked ? 'danger' : 'success'" effect="plain">
              {{ row.is_blocked ? "已封禁" : "已放行" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="alert_name" label="关联告警" min-width="180" show-overflow-tooltip />

        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button
                type="primary"
                link
                :loading="isRowActionLoading(row.action_id)"
                @click="handleVerify(row)"
              >
                {{ row.current_ban_status === "BLOCKED" ? "校验封禁" : "校验放行" }}
              </el-button>

              <el-button
                v-if="row.can_unban"
                type="danger"
                link
                :loading="isRowActionLoading(row.action_id)"
                @click="handleUnban(row)"
              >
                放行
              </el-button>

              <el-button
                v-else-if="row.can_reblock"
                type="warning"
                link
                :loading="isRowActionLoading(row.action_id)"
                @click="handleReblock(row)"
              >
                重新封禁
              </el-button>

              <el-button type="primary" link @click="handleOpenHistory(row)">历史</el-button>
            </div>
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
      v-model="historyDrawerVisible"
      title="历史处置记录"
      size="520px"
      destroy-on-close
    >
      <div v-loading="historyLoading" class="history-drawer">
        <template v-if="historyDetail">
          <div class="history-overview">
            <div class="history-overview__card">
              <div class="history-overview__label">目标 IP</div>
              <div class="history-overview__value">{{ historyDetail.ip_address || "-" }}</div>
            </div>
            <div class="history-overview__card">
              <div class="history-overview__label">当前状态</div>
              <div class="history-overview__value">{{ formatCurrentStatus(historyDetail.current_ban_status) }}</div>
            </div>
            <div class="history-overview__card">
              <div class="history-overview__label">最近动作</div>
              <div class="history-overview__value">{{ formatActionLabel(historyDetail.latest_action_type) }}</div>
            </div>
          </div>

          <el-timeline>
            <el-timeline-item
              v-for="item in historyTimeline"
              :key="`${historyDetail.action_id}-${item.sequence}`"
              :timestamp="item.operated_at"
              :type="timelineType(item)"
              placement="top"
            >
              <div class="timeline-card">
                <div class="timeline-card__title">
                  {{ formatActionLabel(item.action_type) }}
                  <el-tag size="small" effect="plain" :type="currentStatusTagType(item.to_status)">
                    {{ formatCurrentStatus(item.to_status) }}
                  </el-tag>
                </div>
                <div class="timeline-card__meta">状态变化：{{ item.from_status }} -> {{ item.to_status }}</div>
                <div class="timeline-card__meta">操作人：{{ item.operated_by || "-" }}</div>
                <div class="timeline-card__meta">原因：{{ item.reason || "-" }}</div>
              </div>
            </el-timeline-item>
          </el-timeline>
        </template>

        <el-empty v-else description="暂无历史记录" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
// 文件路径：frontend/src/views/BansView.vue
// 作用说明：
// 1. 通过封禁管理接口加载当前状态列表和执行结果。
// 2. 支持放行、重新封禁和规则校验，并在成功后即时刷新列表与历史抽屉。
// 3. 通过执行模式概览和规则校验字段，帮助用户核查封禁是否已下发到 Windows 防火墙。
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { fetchBanDetail, fetchBans, reblockBan, unbanBan, verifyBan } from "@/api/bans";

const loading = ref(false);
const banItems = ref([]);
const actionLoadingMap = reactive({});

const historyDrawerVisible = ref(false);
const historyLoading = ref(false);
const historyDetail = ref(null);

const queryForm = reactive({
  status: "",
  target_ip: ""
});

const pagination = reactive({
  page: 1,
  size: 10,
  total: 0
});

const enforcementProfile = reactive({
  mode: "MOCK",
  backend: "MOCK",
  host_platform: "WINDOWS",
  supports_real_execution: false,
  rule_prefix: "ESG",
  local_ports: [],
  scope_description: ""
});

const blockedCount = computed(() => {
  return banItems.value.filter((item) => item.current_ban_status === "BLOCKED").length;
});

const releasedCount = computed(() => {
  return banItems.value.filter((item) => item.current_ban_status === "RELEASED").length;
});

const verifiedCount = computed(() => {
  return banItems.value.filter((item) => item.verification_status === "VERIFIED").length;
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

const historyTimeline = computed(() => {
  const items = historyDetail.value?.history_actions || [];
  return [...items].reverse();
});

const executionModeTagType = computed(() => {
  return enforcementProfile.mode === "REAL" ? "danger" : "info";
});

function actionTypeTagType(actionType) {
  const normalizedActionType = String(actionType || "").toUpperCase();

  if (["BLOCK_IP", "MANUAL_BLOCK_IP"].includes(normalizedActionType)) {
    return "danger";
  }

  if (["UNBLOCK_IP", "MANUAL_UNBLOCK_IP"].includes(normalizedActionType)) {
    return "success";
  }

  return "info";
}

function formatActionLabel(actionType) {
  const normalizedActionType = String(actionType || "").toUpperCase();
  const labelMap = {
    BLOCK_IP: "自动封禁",
    MANUAL_BLOCK_IP: "人工重新封禁",
    UNBLOCK_IP: "自动放行",
    MANUAL_UNBLOCK_IP: "人工放行"
  };

  return labelMap[normalizedActionType] || normalizedActionType || "-";
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

function formatEnforcementMode(mode) {
  const normalizedMode = String(mode || "").toUpperCase();

  if (normalizedMode === "WEB_BLOCKLIST") {
    return "Web 阻断";
  }

  if (normalizedMode === "REAL") {
    return "真实执行";
  }

  return "模拟执行";
}

function formatEnforcementModeDisplay(mode) {
  const normalizedMode = String(mode || "").toUpperCase();

  if (normalizedMode === "WINDOWS_FIREWALL" || normalizedMode === "REAL") {
    return "Windows 防火墙";
  }

  if (normalizedMode === "WEB_BLOCKLIST") {
    return "Web 阻断";
  }

  if (normalizedMode === "MOCK") {
    return "模拟执行";
  }

  return normalizedMode || "-";
}

function formatEnforcementBackend(backend) {
  const normalizedBackend = String(backend || "").toUpperCase();

  if (normalizedBackend === "WEB_BLOCKLIST") {
    return "Web Blocklist";
  }

  if (normalizedBackend === "WINDOWS_FIREWALL") {
    return "Windows 防火墙";
  }

  if (normalizedBackend === "MOCK") {
    return "模拟后端";
  }

  return normalizedBackend || "-";
}

function formatBlockSource(blockSource) {
  const normalizedBlockSource = String(blockSource || "").toUpperCase();

  if (normalizedBlockSource === "AUTOMATIC") {
    return "自动";
  }

  if (normalizedBlockSource === "MANUAL") {
    return "手动";
  }

  return normalizedBlockSource || "-";
}

function blockSourceTagType(blockSource) {
  const normalizedBlockSource = String(blockSource || "").toUpperCase();
  return normalizedBlockSource === "AUTOMATIC" ? "danger" : "info";
}

function enforcementStatusTagType(status) {
  const normalizedStatus = String(status || "").toUpperCase();

  if (["APPLIED"].includes(normalizedStatus)) {
    return "danger";
  }

  if (["REMOVED"].includes(normalizedStatus)) {
    return "success";
  }

  if (["FAILED"].includes(normalizedStatus)) {
    return "danger";
  }

  if (["PENDING"].includes(normalizedStatus)) {
    return "warning";
  }

  return "info";
}

function formatEnforcementStatus(status) {
  const normalizedStatus = String(status || "").toUpperCase();
  const labelMap = {
    APPLIED: "已下发",
    REMOVED: "已移除",
    FAILED: "执行失败",
    PENDING: "待执行",
    SIMULATED: "模拟执行"
  };

  return labelMap[normalizedStatus] || normalizedStatus || "-";
}

function verificationStatusTagType(status) {
  const normalizedStatus = String(status || "").toUpperCase();

  if (normalizedStatus === "VERIFIED") {
    return "success";
  }

  if (normalizedStatus === "NOT_VERIFIED") {
    return "info";
  }

  if (normalizedStatus === "MISSING") {
    return "warning";
  }

  if (normalizedStatus === "FAILED") {
    return "danger";
  }

  return "info";
}

function formatVerificationStatus(status) {
  const normalizedStatus = String(status || "").toUpperCase();
  const labelMap = {
    VERIFIED: "校验通过",
    NOT_VERIFIED: "未校验",
    MISSING: "规则缺失",
    FAILED: "校验失败"
  };

  return labelMap[normalizedStatus] || normalizedStatus || "-";
}

function timelineType(item) {
  return currentStatusTagType(item?.to_status);
}

function isRowActionLoading(actionId) {
  return Boolean(actionLoadingMap[actionId]);
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

    const profile = data.enforcement_profile || {};
    enforcementProfile.mode = profile.mode || "MOCK";
    enforcementProfile.backend = profile.backend || "MOCK";
    enforcementProfile.host_platform = profile.host_platform || "WINDOWS";
    enforcementProfile.supports_real_execution = Boolean(profile.supports_real_execution);
    enforcementProfile.rule_prefix = profile.rule_prefix || "ESG";
    enforcementProfile.local_ports = profile.local_ports || [];
    enforcementProfile.scope_description = profile.scope_description || "";
  } finally {
    loading.value = false;
  }
}

async function loadHistoryDetail(actionId) {
  historyLoading.value = true;
  try {
    const response = await fetchBanDetail(actionId);
    historyDetail.value = response?.data || null;
  } finally {
    historyLoading.value = false;
  }
}

async function handleOpenHistory(row) {
  historyDrawerVisible.value = true;
  await loadHistoryDetail(row.action_id);
}

async function refreshHistoryIfNeeded(actionId) {
  if (historyDrawerVisible.value && historyDetail.value?.action_id === actionId) {
    await loadHistoryDetail(actionId);
  }
}

async function handleStateToggle(row, toggleType) {
  const isUnban = toggleType === "unban";
  const dialogTitle = isUnban ? "确认放行 / 解封" : "确认重新封禁";
  const dialogMessage = isUnban
    ? `请填写对记录 ${row.action_id} 的放行原因。`
    : `请填写对记录 ${row.action_id} 的重新封禁原因。`;
  const defaultReason = isUnban ? "人工复核后确认放行" : "人工复核后重新封禁";
  const confirmButtonText = isUnban ? "确认放行" : "确认重新封禁";

  try {
    const promptResult = await ElMessageBox.prompt(dialogMessage, dialogTitle, {
      confirmButtonText,
      cancelButtonText: "取消",
      inputType: "textarea",
      inputValue: defaultReason,
      inputPlaceholder: "请输入原因"
    });

    actionLoadingMap[row.action_id] = true;
    const payload = {
      reason: promptResult.value || defaultReason,
      operator: "security_console"
    };

    const response = isUnban
      ? await unbanBan(row.action_id, payload)
      : await reblockBan(row.action_id, payload);

    ElMessage.success(response?.message || (isUnban ? "放行成功" : "重新封禁成功"));
    await loadBans();
    await refreshHistoryIfNeeded(row.action_id);
  } catch (error) {
    if (
      error === "cancel" ||
      error === "close" ||
      error?.action === "cancel" ||
      error?.action === "close"
    ) {
      return;
    }
  } finally {
    actionLoadingMap[row.action_id] = false;
  }
}

async function handleVerify(row) {
  actionLoadingMap[row.action_id] = true;
  try {
    const response = await verifyBan(row.action_id);
    ElMessage.success(response?.message || "规则校验完成");
    await loadBans();
    await refreshHistoryIfNeeded(row.action_id);
  } finally {
    actionLoadingMap[row.action_id] = false;
  }
}

function handleUnban(row) {
  return handleStateToggle(row, "unban");
}

function handleReblock(row) {
  return handleStateToggle(row, "reblock");
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

.page-banner__actions {
  display: flex;
  align-items: center;
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
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary);
}

.summary-card__value--danger {
  color: var(--text-primary);
}

.summary-card__value--warning {
  color: var(--text-primary);
}

.summary-card__value--primary {
  color: var(--text-primary);
}

.summary-card__value--success {
  color: var(--text-primary);
}

.summary-card__hint {
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-secondary);
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

.table-header-tip {
  color: var(--text-secondary);
  font-size: 13px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 0;
}

.history-cell {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.history-summary-text {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.count-stack,
.time-stack {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: var(--text-secondary);
  font-size: 13px;
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.pagination-bar {
  display: flex;
  justify-content: flex-end;
  margin-top: 18px;
}

.history-drawer {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.history-overview {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.history-overview__card {
  padding: 16px;
  border-radius: 16px;
  background: var(--page-bg-accent);
  border: 1px solid var(--panel-border);
}

.history-overview__label {
  font-size: 12px;
  color: var(--text-secondary);
}

.history-overview__value {
  margin-top: 10px;
  font-size: 16px;
  line-height: 1.5;
  color: var(--text-primary);
  word-break: break-word;
}

.timeline-card {
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--page-bg-accent);
  border: 1px solid var(--panel-border);
}

.timeline-card__title {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-primary);
  font-weight: 600;
}

.timeline-card__meta {
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

@media (max-width: 992px) {
  .page-banner {
    flex-direction: column;
    align-items: flex-start;
  }

  .history-overview {
    grid-template-columns: 1fr;
  }
}

</style>
