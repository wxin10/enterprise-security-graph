<template>
  <!--
    文件路径：frontend/src/views/MonitorCenterView.vue
    作用说明：
    1. 展示日志监控中心页面。
    2. 支持一键开启和停止后端 log_watcher.py 监听任务。
    3. 展示监控状态、监听目录、最近处理记录，以及新增的“监控关系图谱”可视化区域。
    4. 图谱区域以业务处理链路方式展示“日志接入 -> 解析适配 -> Neo4j 入库 -> 检测 -> 告警 -> 封禁”的闭环拓扑。
  -->
  <div class="monitor-page app-page">
    <section class="security-panel page-banner">
      <div>
        <h1 class="page-title">日志监控中心</h1>
        <p class="page-subtitle">
          当前页面用于演示“前端开启监控 - 后端持续监听日志目录 - 自动导入 Neo4j - 自动运行检测”的闭环入口，
          并通过处理链路图谱展示系统自动化拓扑。
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
          <div class="summary-card__hint">便于快速确认自动检测是否已执行成功</div>
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

        <div class="table-header-tip">记录数：{{ recentRecords.length }}</div>
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

    <section class="security-panel topology-panel">
      <div class="section-header topology-panel__header">
        <div>
          <h3>自动监控流程图</h3>
          <p>
            基于最近处理批次构建系统自动化流程图，展示“日志接入 -> 适配解析 -> Neo4j 入库 -> 检测 -> 告警 -> 封禁预留”的处理链路。
          </p>
        </div>

        <div class="topology-summary">
          <el-tag type="success" effect="dark">
            成功链路 {{ topologyData.summary.success_batch_count || 0 }}
          </el-tag>
          <el-tag type="danger" effect="dark">
            失败链路 {{ topologyData.summary.failed_batch_count || 0 }}
          </el-tag>
          <el-tag type="warning" effect="dark">
            部分完成 {{ topologyData.summary.partial_batch_count || 0 }}
          </el-tag>
        </div>
      </div>

      <div class="topology-tip-row">
        <div>最近成功批次：{{ topologyData.summary.latest_success_batch_id || "-" }}</div>
        <div>最近失败批次：{{ topologyData.summary.latest_failed_batch_id || "-" }}</div>
        <div>图谱展示批次数：{{ topologyData.summary.displayed_batch_count || 0 }}</div>
      </div>

      <div class="topology-legend">
        <span class="legend-item">
          <i class="legend-dot legend-dot--success"></i>
          最近成功链路高亮
        </span>
        <span class="legend-item">
          <i class="legend-dot legend-dot--danger"></i>
          最近失败链路标红
        </span>
        <span class="legend-item">
          <i class="legend-line legend-line--dashed"></i>
          封禁动作为预留联动节点
        </span>
      </div>

      <div class="topology-chart-shell" v-loading="topologyLoading">
        <div ref="topologyChartRef" class="topology-chart"></div>
        <div v-if="!topologyLoading && topologyData.nodes.length === 0" class="topology-empty">
          当前还没有可展示的监控链路，请先运行日志监听或放入样例日志文件。
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
// 文件路径：frontend/src/views/MonitorCenterView.vue
// 作用说明：
// 1. 管理监控状态、监控配置、最近处理记录和监控关系图谱的数据加载。
// 2. 支持开启/停止日志监控任务，并通过轮询实现接近实时的展示效果。
// 3. 使用 ECharts graph 展示处理链路拓扑，而不是直接展示数据库原始点图。
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import * as echarts from "echarts";

import {
  fetchMonitorConfig,
  fetchMonitorStatus,
  fetchMonitorTopology,
  startMonitor,
  stopMonitor
} from "@/api/monitors";

const pageLoading = ref(false);
const topologyLoading = ref(false);
const recentRecords = ref([]);
const topologyChartRef = ref(null);

let topologyChartInstance = null;
let autoRefreshTimer = null;
let resizeHandler = null;

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

const topologyData = reactive({
  nodes: [],
  links: [],
  categories: [],
  summary: {
    displayed_batch_count: 0,
    success_batch_count: 0,
    failed_batch_count: 0,
    partial_batch_count: 0,
    latest_success_batch_id: "",
    latest_failed_batch_id: "",
    running: false
  }
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

  if (status === "PARTIAL") {
    return "warning";
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

function topologyStatusColor(status) {
  if (status === "FAILED") {
    return "#ff7285";
  }

  if (status === "PARTIAL" || status === "WARNING") {
    return "#ffbf5a";
  }

  if (status === "SUCCESS") {
    return "#5dd598";
  }

  if (status === "ACTIVE" || status === "READY") {
    return "#67a8ff";
  }

  return "#7086a8";
}

function topologyTypeColor(type) {
  const colorMap = {
    incoming_root: "#2b7cff",
    watch_directory: "#468df9",
    log_file: "#33b5ff",
    adapter: "#25d0b5",
    neo4j: "#3fd5a1",
    detection_engine: "#ffb34d",
    alert: "#ff7a86",
    ban_action: "#a3b7d7"
  };

  return colorMap[type] || "#6f86ab";
}

function buildNodeStyle(node) {
  const baseColor = topologyTypeColor(node.type);
  const statusColor = topologyStatusColor(node.status);

  return {
    color: baseColor,
    borderColor: statusColor,
    borderWidth: node.status === "FAILED" ? 3 : 2,
    shadowBlur: node.status === "FAILED" || node.status === "SUCCESS" ? 20 : 12,
    shadowColor: `${statusColor}66`
  };
}

function buildLinkStyle(link) {
  const statusColor = topologyStatusColor(link.status);

  return {
    color: statusColor,
    width: link.highlight ? 4 : 2,
    opacity: link.highlight ? 0.95 : 0.72,
    curveness: link.dashed ? 0.08 : 0.12,
    type: link.dashed ? "dashed" : "solid"
  };
}

function shortenText(text, maxLength = 16) {
  if (!text || text.length <= maxLength) {
    return text || "";
  }

  return `${text.slice(0, maxLength - 1)}…`;
}

function buildTooltipHtml(title, detailLines) {
  const lines = Array.isArray(detailLines) ? detailLines.filter(Boolean) : [];
  const detailHtml = lines.length ? `<div style="margin-top:6px;">${lines.join("<br/>")}</div>` : "";

  return `
    <div style="min-width:220px;">
      <div style="font-size:14px;font-weight:700;color:#eef5ff;">${title}</div>
      ${detailHtml}
    </div>
  `;
}

function calculateNodePositions(nodes) {
  const chartWidth = topologyChartRef.value?.clientWidth || 1200;
  const chartHeight = topologyChartRef.value?.clientHeight || 520;
  const stageRatioMap = {
    incoming_root: 0.06,
    watch_directory: 0.18,
    log_file: 0.34,
    adapter: 0.49,
    neo4j: 0.65,
    detection_engine: 0.79,
    alert: 0.9,
    ban_action: 0.98
  };

  const laneNodes = nodes.filter((item) => ["watch_directory", "log_file", "adapter"].includes(item.type));
  const maxLane = laneNodes.length
    ? Math.max(...laneNodes.map((item) => Number.isFinite(item.lane) ? item.lane : 0))
    : 0;

  const topPadding = 68;
  const bottomPadding = 68;
  const laneCount = Math.max(maxLane + 1, 1);
  const usableHeight = Math.max(chartHeight - topPadding - bottomPadding, 1);
  const rowSpacing = laneCount > 1 ? usableHeight / laneCount : 0;
  const centerY = chartHeight / 2;

  return nodes.reduce((positionMap, item) => {
    const stageRatio = stageRatioMap[item.type] ?? 0.5;
    const x = Math.round(chartWidth * stageRatio);
    const y = ["incoming_root", "neo4j", "detection_engine", "alert", "ban_action"].includes(item.type)
      ? centerY
      : topPadding + ((item.lane || 0) + 0.5) * rowSpacing;

    positionMap[item.id] = { x, y };
    return positionMap;
  }, {});
}

function buildTopologyChartOption() {
  const categories = topologyData.categories || [];
  const categoryIndexMap = categories.reduce((result, item, index) => {
    result[item.name] = index;
    return result;
  }, {});

  const positions = calculateNodePositions(topologyData.nodes);
  const chartNodes = (topologyData.nodes || []).map((item) => ({
    ...item,
    ...positions[item.id],
    category: categoryIndexMap[item.type] ?? 0,
    draggable: false,
    label: {
      show: true,
      color: "#e8f1ff",
      fontSize: 12,
      formatter: shortenText(item.name, 12)
    },
    itemStyle: buildNodeStyle(item)
  }));

  const chartLinks = (topologyData.links || []).map((item) => ({
    ...item,
    lineStyle: buildLinkStyle(item),
    label: {
      show: true,
      color: "#8aa3c8",
      fontSize: 11,
      formatter: item.relation
    }
  }));

  return {
    backgroundColor: "transparent",
    animationDurationUpdate: 300,
    legend: {
      top: 8,
      textStyle: {
        color: "#a9c0e3"
      },
      itemGap: 16,
      data: categories.map((item) => item.label)
    },
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(7, 18, 33, 0.96)",
      borderColor: "rgba(89, 137, 214, 0.2)",
      borderWidth: 1,
      textStyle: {
        color: "#dfe9ff"
      },
      formatter(params) {
        if (params.dataType === "edge") {
          return buildTooltipHtml(params.data.relation || "链路详情", params.data.detail_lines);
        }

        return buildTooltipHtml(params.data.name || "节点详情", params.data.detail_lines);
      }
    },
    series: [
      {
        type: "graph",
        layout: "none",
        roam: true,
        focusNodeAdjacency: true,
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: [6, 10],
        categories: categories.map((item) => ({ name: item.label })),
        data: chartNodes,
        links: chartLinks,
        lineStyle: {
          opacity: 0.8
        },
        emphasis: {
          scale: true,
          lineStyle: {
            width: 4
          }
        }
      }
    ]
  };
}

function ensureTopologyChart() {
  if (!topologyChartRef.value) {
    return;
  }

  if (!topologyChartInstance) {
    topologyChartInstance = echarts.init(topologyChartRef.value);
  }
}

function renderTopologyChart() {
  if (!topologyChartRef.value || topologyData.nodes.length === 0) {
    return;
  }

  ensureTopologyChart();
  topologyChartInstance.setOption(buildTopologyChartOption(), true);
  topologyChartInstance.resize();
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

async function loadMonitorTopology() {
  topologyLoading.value = true;

  try {
    const response = await fetchMonitorTopology();
    const data = response?.data || {};

    topologyData.nodes = data.nodes || [];
    topologyData.links = data.links || [];
    topologyData.categories = data.categories || [];
    topologyData.summary = data.summary || topologyData.summary;

    await nextTick();
    renderTopologyChart();
  } finally {
    topologyLoading.value = false;
  }
}

async function loadMonitorData() {
  pageLoading.value = true;
  actionLoading.refresh = true;

  try {
    await Promise.all([loadMonitorConfig(), loadMonitorStatus(), loadMonitorTopology()]);
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
    await Promise.all([loadMonitorStatus(), loadMonitorTopology()]);
    ElMessage.success("日志监控任务已启动");
  } finally {
    actionLoading.start = false;
  }
}

async function handleStopMonitor() {
  actionLoading.stop = true;

  try {
    await stopMonitor();
    await Promise.all([loadMonitorStatus(), loadMonitorTopology()]);
    ElMessage.success("日志监控任务已停止");
  } finally {
    actionLoading.stop = false;
  }
}

function startAutoRefresh() {
  stopAutoRefresh();
  autoRefreshTimer = window.setInterval(() => {
    Promise.allSettled([loadMonitorStatus(), loadMonitorTopology()]);
  }, 5000);
}

function stopAutoRefresh() {
  if (autoRefreshTimer) {
    window.clearInterval(autoRefreshTimer);
    autoRefreshTimer = null;
  }
}

function disposeTopologyChart() {
  if (topologyChartInstance) {
    topologyChartInstance.dispose();
    topologyChartInstance = null;
  }
}

onMounted(async () => {
  await loadMonitorData();
  startAutoRefresh();

  resizeHandler = () => {
    if (topologyChartInstance) {
      topologyChartInstance.resize();
    }
  };
  window.addEventListener("resize", resizeHandler);
});

onBeforeUnmount(() => {
  stopAutoRefresh();
  if (resizeHandler) {
    window.removeEventListener("resize", resizeHandler);
    resizeHandler = null;
  }
  disposeTopologyChart();
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
.topology-panel,
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

.topology-panel__header {
  margin-bottom: 12px;
}

.topology-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.topology-tip-row {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  color: #8aa3c8;
  font-size: 13px;
  margin-bottom: 14px;
}

.topology-legend {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  color: #a6badb;
  font-size: 13px;
  margin-bottom: 14px;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.legend-dot--success {
  background: #5dd598;
  box-shadow: 0 0 12px rgba(93, 213, 152, 0.45);
}

.legend-dot--danger {
  background: #ff7285;
  box-shadow: 0 0 12px rgba(255, 114, 133, 0.45);
}

.legend-line {
  width: 20px;
  height: 2px;
  display: inline-block;
  background: #8ea6cb;
}

.legend-line--dashed {
  background: linear-gradient(90deg, #8ea6cb 50%, transparent 0) repeat-x;
  background-size: 8px 2px;
}

.topology-chart-shell {
  position: relative;
  min-height: 520px;
  border-radius: 18px;
  overflow: hidden;
  background:
    radial-gradient(circle at top left, rgba(43, 124, 255, 0.12), transparent 30%),
    linear-gradient(180deg, rgba(8, 20, 35, 0.82), rgba(6, 14, 27, 0.94));
  border: 1px solid rgba(84, 129, 194, 0.14);
}

.topology-chart {
  width: 100%;
  height: 520px;
}

.topology-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 24px;
  color: #8aa3c8;
  font-size: 14px;
  line-height: 1.8;
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

  .topology-summary,
  .topology-tip-row,
  .topology-legend {
    flex-direction: column;
    align-items: flex-start;
  }

  .topology-chart-shell,
  .topology-chart {
    min-height: 460px;
    height: 460px;
  }
}
</style>
