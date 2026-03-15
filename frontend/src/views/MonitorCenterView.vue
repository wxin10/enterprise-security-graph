<template>
  <!--
    文件路径：frontend/src/views/MonitorCenterView.vue
    作用说明：
    1. 展示日志监控中心页面。
    2. 支持一键开启和停止后端 log_watcher.py 监听任务。
    3. 展示监控状态、监听目录以及最近处理记录，形成适合答辩演示的自动化监控控制台。
  -->
  <div class="monitor-page app-page">
    <section class="security-panel page-banner">
      <div>
        <h1 class="page-title">日志监控中心</h1>
        <p class="page-subtitle">
          当前页面用于演示“前端开启监控 - 后端持续监听日志目录 - 自动导入 Neo4j - 自动运行检测”的闭环入口。
        </p>
      </div>

      <el-tag :type="monitorStatus.running ? 'success' : 'info'" effect="dark" size="large">
        {{ monitorStatus.running ? "监控运行中" : "监控未启动" }}
      </el-tag>
    </section>

    <el-row :gutter="18" class="summary-grid">
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">当前状态</div>
          <div
            class="summary-card__value"
            :class="monitorStatus.running ? 'summary-card__value--success' : 'summary-card__value--muted'"
          >
            {{ monitorStatus.running ? "运行中" : "已停止" }}
          </div>
          <div class="summary-card__hint">依据 monitor_state.json 与 PID 探测结果实时更新</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">Watcher PID</div>
          <div class="summary-card__value summary-card__value--primary">
            {{ monitorStatus.pid || "-" }}
          </div>
          <div class="summary-card__hint">当前 log_watcher.py 后台监听进程编号</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">最近处理时间</div>
          <div class="summary-card__value summary-card__value--warning summary-card__value--small">
            {{ monitorStatus.latest_processed_at || "-" }}
          </div>
          <div class="summary-card__hint">来自 data/runtime/batches/*/status.json 的最近批次时间</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">最近检测状态</div>
          <div class="summary-card__value" :class="detectionStatusClass">
            {{ monitorStatus.latest_detection_status || "IDLE" }}
          </div>
          <div class="summary-card__hint">便于前端快速确认自动检测是否已执行成功</div>
        </div>
      </el-col>
    </el-row>

    <section class="security-panel action-panel">
      <div class="section-header">
        <div>
          <h3>监控控制</h3>
          <p>当前版本直接通过 subprocess 启动 scripts/log_watcher.py，优先保证本地最小可运行演示。</p>
        </div>
      </div>

      <div class="action-row">
        <div class="action-row__left">
          <div class="action-field">
            <span class="action-field__label">监听间隔（秒）</span>
            <el-input-number
              v-model="controlForm.interval_seconds"
              :min="1"
              :max="3600"
              controls-position="right"
            />
          </div>
        </div>

        <div class="action-row__right">
          <el-button
            type="success"
            :loading="actionLoading.start"
            :disabled="monitorStatus.running"
            @click="handleStartMonitor"
          >
            开启监控
          </el-button>

          <el-button
            type="danger"
            :loading="actionLoading.stop"
            :disabled="!monitorStatus.running"
            @click="handleStopMonitor"
          >
            停止监控
          </el-button>

          <el-button type="primary" plain :loading="actionLoading.refresh" @click="loadMonitorData">
            刷新状态
          </el-button>
        </div>
      </div>

      <div class="action-meta">
        <div>启动时间：{{ monitorStatus.started_at || "-" }}</div>
        <div>最近处理文件数：{{ monitorStatus.processed_file_count || 0 }}</div>
        <div>当前轮询间隔：{{ monitorStatus.interval_seconds || configData.default_interval_seconds || 5 }} 秒</div>
      </div>
    </section>

    <section class="security-panel directory-panel">
      <div class="section-header">
        <div>
          <h3>监听目录</h3>
          <p>后端会扫描 incoming 根目录下的多个子目录，实现多源日志自动接入。</p>
        </div>
      </div>

      <div class="directory-root">
        <span class="directory-root__label">incoming 根目录</span>
        <code class="directory-root__value">{{ configData.incoming_root || "-" }}</code>
      </div>

      <div class="directory-list">
        <el-tag
          v-for="item in configData.watch_directories"
          :key="item"
          class="directory-tag"
          effect="plain"
        >
          {{ item }}
        </el-tag>
      </div>
    </section>

    <section class="security-panel table-panel">
      <div class="section-header">
        <div>
          <h3>最近处理记录</h3>
          <p>直接复用 log_watcher 生成的批次状态文件，不额外引入新的数据库表或缓存层。</p>
        </div>

        <div class="table-header-tip">
          记录数：{{ recentRecords.length }}
        </div>
      </div>

      <el-table :data="recentRecords" v-loading="pageLoading" stripe>
        <el-table-column prop="batch_id" label="批次编号" min-width="200" show-overflow-tooltip />
        <el-table-column prop="source_file" label="原始文件" min-width="280" show-overflow-tooltip />

        <el-table-column label="处理状态" min-width="110">
          <template #default="{ row }">
            <el-tag :type="recordStatusTagType(row.status)" effect="dark">
              {{ row.status || "-" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="检测状态" min-width="120">
          <template #default="{ row }">
            <el-tag :type="detectionTagType(row.detection_status)" effect="plain">
              {{ row.detection_status || "-" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="processed_at" label="处理时间" min-width="170" />
        <el-table-column prop="failed_step" label="失败步骤" min-width="120" />
        <el-table-column prop="parse_error_count" label="解析异常数" min-width="110" />
      </el-table>
    </section>
  </div>
</template>

<script setup>
// 文件路径：frontend/src/views/MonitorCenterView.vue
// 作用说明：
// 1. 管理监控状态、监控配置和最近处理记录的数据加载。
// 2. 支持开启/停止日志监控任务，并通过轮询实现接近实时的展示效果。
// 3. 保持当前页面风格与仪表盘、告警页、封禁页一致。
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";

import {
  fetchMonitorConfig,
  fetchMonitorStatus,
  startMonitor,
  stopMonitor
} from "@/api/monitors";

const pageLoading = ref(false);
const recentRecords = ref([]);
let autoRefreshTimer = null;

const actionLoading = reactive({
  start: false,
  stop: false,
  refresh: false
});

const controlForm = reactive({
  interval_seconds: 5
});

const configData = reactive({
  incoming_root: "",
  watch_directories: [],
  default_interval_seconds: 5,
  runtime_state_file: "",
  watcher_log_file: ""
});

const monitorStatus = reactive({
  running: false,
  pid: null,
  started_at: "",
  interval_seconds: 5,
  watch_directories: [],
  processed_file_count: 0,
  latest_processed_at: "",
  latest_detection_status: "IDLE",
  recent_records: []
});

const detectionStatusClass = computed(() => {
  if (monitorStatus.latest_detection_status === "SUCCESS") {
    return "summary-card__value--success";
  }

  if (monitorStatus.latest_detection_status === "FAILED") {
    return "summary-card__value--danger";
  }

  if (monitorStatus.latest_detection_status === "NOT_RUN") {
    return "summary-card__value--warning";
  }

  return "summary-card__value--muted";
});

function recordStatusTagType(status) {
  if (status === "SUCCESS") {
    return "success";
  }

  if (status === "FAILED") {
    return "danger";
  }

  return "info";
}

function detectionTagType(status) {
  if (status === "SUCCESS") {
    return "success";
  }

  if (status === "FAILED") {
    return "danger";
  }

  if (status === "NOT_RUN") {
    return "warning";
  }

  return "info";
}

async function loadMonitorConfig() {
  const response = await fetchMonitorConfig();
  const data = response?.data || {};

  configData.incoming_root = data.incoming_root || "";
  configData.watch_directories = data.watch_directories || [];
  configData.default_interval_seconds = data.default_interval_seconds || 5;
  configData.runtime_state_file = data.runtime_state_file || "";
  configData.watcher_log_file = data.watcher_log_file || "";

  if (!controlForm.interval_seconds) {
    controlForm.interval_seconds = configData.default_interval_seconds;
  }
}

async function loadMonitorStatus() {
  const response = await fetchMonitorStatus();
  const data = response?.data || {};

  monitorStatus.running = Boolean(data.running);
  monitorStatus.pid = data.pid ?? null;
  monitorStatus.started_at = data.started_at || "";
  monitorStatus.interval_seconds = data.interval_seconds || configData.default_interval_seconds || 5;
  monitorStatus.watch_directories = data.watch_directories || [];
  monitorStatus.processed_file_count = data.processed_file_count || 0;
  monitorStatus.latest_processed_at = data.latest_processed_at || "";
  monitorStatus.latest_detection_status = data.latest_detection_status || "IDLE";
  monitorStatus.recent_records = data.recent_records || [];

  recentRecords.value = monitorStatus.recent_records;
}

async function loadMonitorData() {
  pageLoading.value = true;
  actionLoading.refresh = true;

  try {
    await Promise.all([loadMonitorConfig(), loadMonitorStatus()]);
  } finally {
    pageLoading.value = false;
    actionLoading.refresh = false;
  }
}

async function handleStartMonitor() {
  actionLoading.start = true;

  try {
    await startMonitor({
      interval_seconds: controlForm.interval_seconds
    });
    await loadMonitorStatus();
    ElMessage.success("日志监控任务已启动");
  } finally {
    actionLoading.start = false;
  }
}

async function handleStopMonitor() {
  actionLoading.stop = true;

  try {
    await stopMonitor();
    await loadMonitorStatus();
    ElMessage.success("日志监控任务已停止");
  } finally {
    actionLoading.stop = false;
  }
}

function startAutoRefresh() {
  stopAutoRefresh();
  autoRefreshTimer = window.setInterval(() => {
    loadMonitorStatus();
  }, 5000);
}

function stopAutoRefresh() {
  if (autoRefreshTimer) {
    window.clearInterval(autoRefreshTimer);
    autoRefreshTimer = null;
  }
}

onMounted(async () => {
  await loadMonitorData();
  startAutoRefresh();
});

onBeforeUnmount(() => {
  stopAutoRefresh();
});
</script>

<style scoped>
.monitor-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-banner,
.action-panel,
.directory-panel,
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
  font-size: 30px;
  font-weight: 700;
  color: #eef5ff;
}

.summary-card__value--small {
  font-size: 16px;
  line-height: 1.5;
  word-break: break-word;
}

.summary-card__value--success {
  color: #5dd598;
}

.summary-card__value--danger {
  color: #ff7285;
}

.summary-card__value--warning {
  color: #ffbf5a;
}

.summary-card__value--primary {
  color: #67a8ff;
}

.summary-card__value--muted {
  color: #8ea6cb;
}

.summary-card__hint {
  margin-top: 10px;
  color: #7f98be;
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
  color: #ecf4ff;
}

.section-header p {
  margin: 8px 0 0;
  color: #8aa3c8;
  font-size: 13px;
  line-height: 1.7;
}

.action-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
}

.action-row__left,
.action-row__right {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.action-field {
  display: flex;
  align-items: center;
  gap: 12px;
}

.action-field__label {
  font-size: 14px;
  color: #b8cae6;
}

.action-meta {
  margin-top: 16px;
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  color: #8aa3c8;
  font-size: 13px;
}

.directory-root {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.directory-root__label {
  font-size: 13px;
  color: #8aa3c8;
}

.directory-root__value {
  display: block;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(8, 20, 35, 0.92);
  border: 1px solid rgba(84, 129, 194, 0.14);
  color: #dce8ff;
  word-break: break-all;
}

.directory-list {
  margin-top: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.directory-tag {
  padding: 6px 4px;
}

.table-header-tip {
  color: #8aa3c8;
  font-size: 13px;
}

@media (max-width: 992px) {
  .page-banner {
    flex-direction: column;
    align-items: flex-start;
  }

  .action-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

