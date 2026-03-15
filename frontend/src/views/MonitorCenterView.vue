<template>
  <!-- 文件路径：frontend/src/views/MonitorCenterView.vue。作用：保留日志监控中心原有功能，并把底部流程图增强为可拖拽、可高亮、可查看节点详情的交互式图谱。 -->
  <div class="monitor-page app-page">
    <section class="security-panel page-banner">
      <div>
        <h1 class="page-title">日志监控中心</h1>
        <p class="page-subtitle">
          当前页面用于演示“前端开启监控 - 后端持续监听日志目录 - 自动导入 Neo4j - 自动运行检测”的闭环入口，并通过自动监控流程图展示系统自动化拓扑。
        </p>
      </div>
      <el-tag :type="monitorStatus.running ? 'success' : 'info'" effect="dark" size="large">
        {{ monitorStatus.running ? "监控运行中" : "监控未启动" }}
      </el-tag>
    </section>

    <el-row :gutter="18" class="summary-grid">
      <el-col v-for="item in summaryCards" :key="item.label" :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">{{ item.label }}</div>
          <div class="summary-card__value" :class="item.className">{{ item.value }}</div>
          <div class="summary-card__hint">{{ item.hint }}</div>
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
            <el-input-number v-model="controlForm.interval_seconds" :min="1" :max="3600" controls-position="right" />
          </div>
        </div>
        <div class="action-row__right">
          <el-button type="success" :loading="actionLoading.start" :disabled="monitorStatus.running" @click="handleStartMonitor">开启监控</el-button>
          <el-button type="danger" :loading="actionLoading.stop" :disabled="!monitorStatus.running" @click="handleStopMonitor">停止监控</el-button>
          <el-button type="primary" plain :loading="actionLoading.refresh" @click="loadMonitorData">刷新状态</el-button>
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
        <el-tag v-for="item in configData.watch_directories" :key="item" class="directory-tag" effect="plain">{{ item }}</el-tag>
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
          <template #default="{ row }"><el-tag :type="recordStatusTagType(row.status)" effect="dark">{{ row.status || "-" }}</el-tag></template>
        </el-table-column>
        <el-table-column label="检测状态" min-width="120">
          <template #default="{ row }"><el-tag :type="detectionTagType(row.detection_status)" effect="plain">{{ row.detection_status || "-" }}</el-tag></template>
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
          <p>展示“日志接入 -> 适配解析 -> Neo4j 入库 -> 检测 -> 告警 -> 封禁预留”的系统闭环，可拖拽节点并点击查看相邻链路。</p>
        </div>
        <div class="topology-summary">
          <el-tag type="success" effect="dark">成功链路 {{ topologyData.summary.success_batch_count || 0 }}</el-tag>
          <el-tag type="danger" effect="dark">失败链路 {{ topologyData.summary.failed_batch_count || 0 }}</el-tag>
          <el-tag type="warning" effect="dark">部分完成 {{ topologyData.summary.partial_batch_count || 0 }}</el-tag>
        </div>
      </div>
      <div class="topology-tip-row">
        <div>最近成功批次：{{ topologyData.summary.latest_success_batch_id || "-" }}</div>
        <div>最近失败批次：{{ topologyData.summary.latest_failed_batch_id || "-" }}</div>
        <div>图谱显示批次数：{{ topologyData.summary.displayed_batch_count || 0 }}</div>
      </div>
      <div class="topology-legend">
        <span class="legend-item"><i class="legend-dot legend-dot--success"></i>最近成功链路高亮</span>
        <span class="legend-item"><i class="legend-dot legend-dot--danger"></i>最近失败链路标红</span>
        <span class="legend-item"><i class="legend-line legend-line--dashed"></i>封禁动作为预留联动节点</span>
        <span class="legend-item legend-item--tip">提示：支持拖拽节点、滚轮缩放、点击节点高亮邻接关系</span>
      </div>
      <div class="topology-layout-tools">
        <el-tag size="small" effect="dark" :type="topologyLayoutMode === 'force' ? 'warning' : 'success'">
          {{ topologyLayoutMode === "force" ? "自动排布中" : "自由拖动模式" }}
        </el-tag>
        <el-button type="primary" plain size="small" @click="handleTopologyRelayout">重新布局</el-button>
      </div>
      <div class="topology-chart-shell" v-loading="topologyLoading">
        <div ref="topologyChartRef" class="topology-chart"></div>
        <div v-if="!topologyLoading && topologyData.nodes.length === 0" class="topology-empty">当前还没有可展示的监控链路，请先运行日志监听或放入样例日志文件。</div>
      </div>
      <div class="security-panel topology-detail-card">
        <template v-if="selectedTopologyNodeMeta">
          <div class="detail-card__header">
            <div>
              <div class="detail-card__title">{{ selectedTopologyNodeMeta.name }}</div>
              <div class="detail-card__subtitle">{{ selectedTopologyNodeMeta.typeLabel }}</div>
            </div>
            <el-tag effect="dark" :type="selectedTopologyNodeMeta.tagType">{{ selectedTopologyNodeMeta.statusText }}</el-tag>
          </div>
          <div class="detail-card__grid">
            <div class="detail-card__item"><div class="detail-card__label">节点编号</div><div class="detail-card__value">{{ selectedTopologyNodeMeta.id }}</div></div>
            <div class="detail-card__item"><div class="detail-card__label">关联边数</div><div class="detail-card__value">{{ selectedTopologyNodeMeta.relatedEdgeCount }}</div></div>
            <div class="detail-card__item detail-card__item--wide">
              <div class="detail-card__label">关键属性</div>
              <div class="detail-card__value detail-card__value--multiline">
                <template v-if="selectedTopologyNodeMeta.detailLines.length > 0"><div v-for="line in selectedTopologyNodeMeta.detailLines" :key="line">{{ line }}</div></template>
                <template v-else>当前节点暂无额外说明</template>
              </div>
            </div>
          </div>
        </template>
        <template v-else><div class="detail-card__placeholder">点击流程图中的任意节点后，这里会展示节点类型、关键属性和该节点在自动监控闭环中的作用。</div></template>
      </div>
    </section>
  </div>
</template>

<script setup>
// 文件路径：frontend/src/views/MonitorCenterView.vue。作用：维持监控启停与状态展示不变，并把底部流程图增强为可探索的力导向关系图；同时在自动刷新时尽量保留节点布局和拖拽结果。
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import * as echarts from "echarts";
import { fetchMonitorConfig, fetchMonitorStatus, fetchMonitorTopology, startMonitor, stopMonitor } from "@/api/monitors";

const pageLoading = ref(false);
const topologyLoading = ref(false);
const recentRecords = ref([]);
const topologyChartRef = ref(null);
const selectedTopologyNode = ref(null);
const topologyLayoutMode = ref("force");
let topologyChartInstance = null;
let autoRefreshTimer = null;
let resizeHandler = null;
let topologyBlankClickHandler = null;
let topologyFreezeAfterNextFinished = true;
const topologyNodePositionState = {};

const actionLoading = reactive({ start: false, stop: false, refresh: false });
const controlForm = reactive({ interval_seconds: 5 });
const configData = reactive({ incoming_root: "", watch_directories: [], default_interval_seconds: 5, runtime_state_file: "", watcher_log_file: "" });
const monitorStatus = reactive({ running: false, pid: null, started_at: "", interval_seconds: 5, watch_directories: [], processed_file_count: 0, latest_processed_at: "", latest_detection_status: "IDLE", recent_records: [] });
const topologyData = reactive({ nodes: [], links: [], categories: [], summary: { displayed_batch_count: 0, success_batch_count: 0, failed_batch_count: 0, partial_batch_count: 0, latest_success_batch_id: "", latest_failed_batch_id: "", running: false } });

const detectionStatusClass = computed(() => monitorStatus.latest_detection_status === "SUCCESS" ? "summary-card__value--success" : monitorStatus.latest_detection_status === "FAILED" ? "summary-card__value--danger" : monitorStatus.latest_detection_status === "NOT_RUN" ? "summary-card__value--warning" : "summary-card__value--muted");
const summaryCards = computed(() => [
  { label: "当前状态", value: monitorStatus.running ? "运行中" : "已停止", className: monitorStatus.running ? "summary-card__value--success" : "summary-card__value--muted", hint: "依据 monitor_state.json 与 PID 探测结果实时更新" },
  { label: "Watcher PID", value: monitorStatus.pid || "-", className: "summary-card__value--primary", hint: "当前 log_watcher.py 后台监听进程编号" },
  { label: "最近处理时间", value: monitorStatus.latest_processed_at || "-", className: "summary-card__value--warning summary-card__value--small", hint: "来自 data/runtime/batches/*/status.json 的最近批次时间" },
  { label: "最近检测状态", value: monitorStatus.latest_detection_status || "IDLE", className: detectionStatusClass.value, hint: "便于快速确认自动检测是否已执行成功" }
]);
const selectedTopologyNodeMeta = computed(() => {
  if (!selectedTopologyNode.value) return null;
  const currentNode = selectedTopologyNode.value;
  return {
    id: currentNode.id || "-",
    name: currentNode.name || "未命名节点",
    typeLabel: topologyTypeLabel(currentNode.type),
    statusText: currentNode.status || "NORMAL",
    tagType: recordStatusTagType(currentNode.status || "INFO"),
    relatedEdgeCount: (topologyData.links || []).filter((item) => item.source === currentNode.id || item.target === currentNode.id).length,
    detailLines: buildTopologyDetailLines(currentNode)
  };
});

function recordStatusTagType(status) { return status === "SUCCESS" ? "success" : status === "FAILED" ? "danger" : status === "PARTIAL" || status === "WARNING" ? "warning" : "info"; }
function detectionTagType(status) { return status === "SUCCESS" ? "success" : status === "FAILED" ? "danger" : status === "NOT_RUN" ? "warning" : "info"; }
function topologyStatusColor(status) { return status === "FAILED" ? "#ff7285" : status === "PARTIAL" || status === "WARNING" ? "#ffbf5a" : status === "SUCCESS" ? "#5dd598" : status === "ACTIVE" || status === "READY" ? "#67a8ff" : "#7086a8"; }
function topologyTypeColor(type) { return ({ incoming_root: "#2b7cff", watch_directory: "#468df9", log_file: "#33b5ff", adapter: "#25d0b5", neo4j: "#3fd5a1", detection_engine: "#ffb34d", alert: "#ff7a86", ban_action: "#a3b7d7" }[type] || "#6f86ab"); }
function topologyTypeLabel(type) { return ({ incoming_root: "incoming 根目录", watch_directory: "监听子目录", log_file: "处理日志文件", adapter: "日志适配器", neo4j: "Neo4j 图数据库", detection_engine: "检测引擎", alert: "告警节点", ban_action: "封禁预留节点" }[type] || "流程节点"); }
function shortenText(text, maxLength = 16) { return !text || text.length <= maxLength ? (text || "") : `${text.slice(0, maxLength - 3)}...`; }
function buildTooltipHtml(title, detailLines) { const lines = Array.isArray(detailLines) ? detailLines.filter(Boolean) : []; return `<div style="min-width:220px;max-width:360px;"><div style="font-size:14px;font-weight:700;color:#eef5ff;">${title}</div>${lines.length ? `<div style="margin-top:6px;">${lines.join("<br/>")}</div>` : ""}</div>`; }
function buildTopologyDetailLines(node) { if (Array.isArray(node?.detail_lines) && node.detail_lines.length) return node.detail_lines.filter(Boolean); return [node?.type ? `节点类型：${topologyTypeLabel(node.type)}` : "", node?.status ? `当前状态：${node.status}` : ""].filter(Boolean); }
function buildAdjacencyMap(links) { const map = new Map(); links.forEach((item) => { if (!map.has(item.source)) map.set(item.source, new Set()); if (!map.has(item.target)) map.set(item.target, new Set()); map.get(item.source).add(item.target); map.get(item.target).add(item.source); }); return map; }
function isNodeRelated(nodeId, selectedId, adjacencyMap) { return !selectedId || nodeId === selectedId || adjacencyMap.get(selectedId)?.has(nodeId) || false; }
function isDirectlyConnected(link, selectedId) { return !selectedId || link.source === selectedId || link.target === selectedId; }
function calculateSeedPositions(nodes) {
  const chartWidth = topologyChartRef.value?.clientWidth || 1200;
  const chartHeight = topologyChartRef.value?.clientHeight || 520;
  const stageRatioMap = { incoming_root: 0.06, watch_directory: 0.18, log_file: 0.34, adapter: 0.49, neo4j: 0.65, detection_engine: 0.79, alert: 0.9, ban_action: 0.98 };
  const laneNodes = nodes.filter((item) => ["watch_directory", "log_file", "adapter"].includes(item.type));
  const maxLane = laneNodes.length ? Math.max(...laneNodes.map((item) => Number.isFinite(item.lane) ? item.lane : 0)) : 0;
  const topPadding = 68; const bottomPadding = 68; const laneCount = Math.max(maxLane + 1, 1); const usableHeight = Math.max(chartHeight - topPadding - bottomPadding, 1); const rowSpacing = laneCount > 1 ? usableHeight / laneCount : 0; const centerY = chartHeight / 2;
  return nodes.reduce((map, item) => { const x = Math.round(chartWidth * (stageRatioMap[item.type] ?? 0.5)); const y = ["incoming_root", "neo4j", "detection_engine", "alert", "ban_action"].includes(item.type) ? centerY : topPadding + ((item.lane || 0) + 0.5) * rowSpacing; map[item.id] = { x, y }; return map; }, {});
}
function syncSelectedTopologyNode() { if (!selectedTopologyNode.value?.id) return; const latestNode = (topologyData.nodes || []).find((item) => item.id === selectedTopologyNode.value.id); selectedTopologyNode.value = latestNode || null; }
function cleanupTopologyNodePositionState() { const activeIds = new Set((topologyData.nodes || []).map((item) => item.id)); Object.keys(topologyNodePositionState).forEach((id) => { if (!activeIds.has(id)) delete topologyNodePositionState[id]; }); }
function clearTopologyNodePositionState() { Object.keys(topologyNodePositionState).forEach((id) => { delete topologyNodePositionState[id]; }); }
function hasStableTopologyPositions(nodes) { return nodes.length > 0 && nodes.every((item) => { const position = topologyNodePositionState[item.id]; return position && Number.isFinite(position.x) && Number.isFinite(position.y); }); }
function prepareTopologyLayoutMode(forceRelayout = false) { cleanupTopologyNodePositionState(); const nodes = topologyData.nodes || []; if (!nodes.length) { topologyLayoutMode.value = "none"; topologyFreezeAfterNextFinished = false; return; } if (forceRelayout) { topologyLayoutMode.value = "force"; topologyFreezeAfterNextFinished = true; return; } const canUseFrozenLayout = hasStableTopologyPositions(nodes); topologyLayoutMode.value = canUseFrozenLayout ? "none" : "force"; topologyFreezeAfterNextFinished = !canUseFrozenLayout; }
function captureTopologyNodePositions() { if (!topologyChartInstance) return; (topologyChartInstance.getOption()?.series?.[0]?.data || []).forEach((item) => { if (item?.id && Number.isFinite(item.x) && Number.isFinite(item.y)) topologyNodePositionState[item.id] = { x: item.x, y: item.y }; }); }
function handleTopologyRelayout() { clearTopologyNodePositionState(); prepareTopologyLayoutMode(true); renderTopologyChart({ forceRelayout: true }); }
function buildTopologyChartOption() {
  const categories = topologyData.categories || []; const categoryIndexMap = categories.reduce((result, item, index) => { result[item.name] = index; return result; }, {});
  const selectedId = selectedTopologyNode.value?.id || ""; const adjacencyMap = buildAdjacencyMap(topologyData.links || []); const seedPositions = calculateSeedPositions(topologyData.nodes || []);
  const chartNodes = (topologyData.nodes || []).map((item) => {
    const isSelected = selectedId === item.id; const related = isNodeRelated(item.id, selectedId, adjacencyMap); const rememberedPosition = topologyNodePositionState[item.id];
    return { ...item, ...(rememberedPosition || seedPositions[item.id] || {}), category: categoryIndexMap[item.type] ?? 0, draggable: true, cursor: "move", symbolSize: item.symbolSize || (item.type === "alert" ? 72 : 58), label: { show: true, position: "bottom", distance: 8, color: related ? "#e8f1ff" : "rgba(232, 241, 255, 0.32)", fontSize: isSelected ? 13 : 12, formatter: shortenText(item.name, 14) }, itemStyle: { color: topologyTypeColor(item.type), borderColor: topologyStatusColor(item.status), borderWidth: isSelected ? 4 : item.status === "FAILED" ? 3 : 2, shadowBlur: isSelected ? 30 : item.status === "FAILED" || item.status === "SUCCESS" ? 20 : 12, shadowColor: `${topologyStatusColor(item.status)}66`, opacity: related ? 1 : 0.2 } };
  });
  const chartLinks = (topologyData.links || []).map((item) => { const directEdge = isDirectlyConnected(item, selectedId); return { ...item, lineStyle: { color: topologyStatusColor(item.status), width: selectedId ? (directEdge ? 4 : 1.2) : item.highlight ? 4 : 2, opacity: selectedId ? (directEdge ? 0.95 : 0.08) : item.highlight ? 0.95 : 0.72, curveness: item.dashed ? 0.08 : 0.12, type: item.dashed ? "dashed" : "solid" }, label: { show: Boolean(selectedId && directEdge), color: "#8aa3c8", fontSize: 11, formatter: item.relation } }; });
  return {
    backgroundColor: "transparent",
    animationDurationUpdate: 450,
    animationEasingUpdate: "quinticInOut",
    legend: { top: 8, textStyle: { color: "#a9c0e3" }, itemGap: 16, data: categories.map((item) => item.label) },
    tooltip: { trigger: "item", backgroundColor: "rgba(7, 18, 33, 0.96)", borderColor: "rgba(89, 137, 214, 0.2)", borderWidth: 1, textStyle: { color: "#dfe9ff" }, formatter(params) { return params.dataType === "edge" ? buildTooltipHtml(params.data.relation || "链路详情", params.data.detail_lines) : buildTooltipHtml(params.data.name || "节点详情", params.data.detail_lines); } },
    series: [{ type: "graph", layout: topologyLayoutMode.value, roam: true, draggable: true, focusNodeAdjacency: true, edgeSymbol: ["none", "arrow"], edgeSymbolSize: [6, 10], labelLayout: { hideOverlap: true }, ...(topologyLayoutMode.value === "force" ? { force: { repulsion: 820, gravity: 0.02, edgeLength: [160, 300], friction: 0.12, layoutAnimation: true, preventOverlap: true } } : {}), scaleLimit: { min: 0.45, max: 2.4 }, categories: categories.map((item) => ({ name: item.label })), data: chartNodes, links: chartLinks, lineStyle: { opacity: 0.82 }, emphasis: { focus: "adjacency", scale: true, lineStyle: { width: 4 } }, blur: { itemStyle: { opacity: 0.12 }, lineStyle: { opacity: 0.05 }, label: { opacity: 0.2 } } }]
  };
}
function bindTopologyChartEvents() {
  if (!topologyChartInstance) return;
  topologyChartInstance.off("click"); topologyChartInstance.off("finished"); topologyChartInstance.off("mouseup");
  topologyChartInstance.on("click", (params) => { if (params?.dataType === "node") { selectedTopologyNode.value = params.data; renderTopologyChart(); } });
  topologyChartInstance.on("finished", () => { captureTopologyNodePositions(); if (topologyLayoutMode.value === "force" && topologyFreezeAfterNextFinished) { topologyFreezeAfterNextFinished = false; topologyLayoutMode.value = "none"; renderTopologyChart(); } });
  topologyChartInstance.on("mouseup", captureTopologyNodePositions);
  if (topologyBlankClickHandler) topologyChartInstance.getZr().off("click", topologyBlankClickHandler);
  topologyBlankClickHandler = (event) => { if (!event.target) { selectedTopologyNode.value = null; renderTopologyChart(); } };
  topologyChartInstance.getZr().on("click", topologyBlankClickHandler);
}
function ensureTopologyChart() { if (topologyChartRef.value && !topologyChartInstance) { topologyChartInstance = echarts.init(topologyChartRef.value); bindTopologyChartEvents(); } }
function renderTopologyChart(options = {}) { prepareTopologyLayoutMode(options.forceRelayout === true); syncSelectedTopologyNode(); if (!topologyChartRef.value || topologyData.nodes.length === 0) { if (topologyChartInstance) topologyChartInstance.clear(); return; } ensureTopologyChart(); topologyChartInstance.setOption(buildTopologyChartOption(), true); topologyChartInstance.resize(); }
async function loadMonitorConfig() { const response = await fetchMonitorConfig(); const data = response?.data || {}; Object.assign(configData, { incoming_root: data.incoming_root || "", watch_directories: data.watch_directories || [], default_interval_seconds: data.default_interval_seconds || 5, runtime_state_file: data.runtime_state_file || "", watcher_log_file: data.watcher_log_file || "" }); if (!controlForm.interval_seconds) controlForm.interval_seconds = configData.default_interval_seconds; }
async function loadMonitorStatus() { const response = await fetchMonitorStatus(); const data = response?.data || {}; Object.assign(monitorStatus, { running: Boolean(data.running), pid: data.pid ?? null, started_at: data.started_at || "", interval_seconds: data.interval_seconds || configData.default_interval_seconds || 5, watch_directories: data.watch_directories || [], processed_file_count: data.processed_file_count || 0, latest_processed_at: data.latest_processed_at || "", latest_detection_status: data.latest_detection_status || "IDLE", recent_records: data.recent_records || [] }); recentRecords.value = monitorStatus.recent_records; }
async function loadMonitorTopology() { topologyLoading.value = true; try { const response = await fetchMonitorTopology(); const data = response?.data || {}; topologyData.nodes = data.nodes || []; topologyData.links = data.links || []; topologyData.categories = data.categories || []; topologyData.summary = data.summary || topologyData.summary; await nextTick(); renderTopologyChart(); } finally { topologyLoading.value = false; } }
async function loadMonitorData() { pageLoading.value = true; actionLoading.refresh = true; try { await Promise.all([loadMonitorConfig(), loadMonitorStatus(), loadMonitorTopology()]); } finally { pageLoading.value = false; actionLoading.refresh = false; } }
async function handleStartMonitor() { actionLoading.start = true; try { await startMonitor({ interval_seconds: controlForm.interval_seconds }); await Promise.all([loadMonitorStatus(), loadMonitorTopology()]); ElMessage.success("日志监控任务已启动"); } finally { actionLoading.start = false; } }
async function handleStopMonitor() { actionLoading.stop = true; try { await stopMonitor(); await Promise.all([loadMonitorStatus(), loadMonitorTopology()]); ElMessage.success("日志监控任务已停止"); } finally { actionLoading.stop = false; } }
function startAutoRefresh() { stopAutoRefresh(); autoRefreshTimer = window.setInterval(() => { Promise.allSettled([loadMonitorStatus(), loadMonitorTopology()]); }, 5000); }
function stopAutoRefresh() { if (autoRefreshTimer) { window.clearInterval(autoRefreshTimer); autoRefreshTimer = null; } }
function disposeTopologyChart() { if (!topologyChartInstance) return; if (topologyBlankClickHandler) { topologyChartInstance.getZr().off("click", topologyBlankClickHandler); topologyBlankClickHandler = null; } topologyChartInstance.dispose(); topologyChartInstance = null; }
onMounted(async () => { await loadMonitorData(); startAutoRefresh(); resizeHandler = () => { if (topologyChartInstance) topologyChartInstance.resize(); }; window.addEventListener("resize", resizeHandler); });
onBeforeUnmount(() => { stopAutoRefresh(); if (resizeHandler) { window.removeEventListener("resize", resizeHandler); resizeHandler = null; } disposeTopologyChart(); });
</script>

<style scoped>
.monitor-page{display:flex;flex-direction:column;gap:18px}.page-banner,.action-panel,.directory-panel,.table-panel,.topology-panel,.summary-card{padding:20px}.page-banner{display:flex;align-items:center;justify-content:space-between;gap:18px}.summary-grid :deep(.el-col){margin-bottom:18px}.summary-card__label,.directory-root__label,.table-header-tip,.detail-card__label{font-size:13px;color:#8aa3c8}.summary-card__value{margin-top:12px;font-size:30px;font-weight:700;color:#eef5ff}.summary-card__value--small{font-size:16px;line-height:1.5;word-break:break-word}.summary-card__value--success{color:#5dd598}.summary-card__value--danger{color:#ff7285}.summary-card__value--warning{color:#ffbf5a}.summary-card__value--primary{color:#67a8ff}.summary-card__value--muted{color:#8ea6cb}.summary-card__hint{margin-top:10px;color:#7f98be;font-size:12px;line-height:1.7}.section-header{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:16px}.section-header h3,.detail-card__title{margin:0;font-size:18px;color:#ecf4ff;font-weight:700}.section-header p,.detail-card__subtitle,.legend-item--tip{margin:8px 0 0;color:#8aa3c8;font-size:13px;line-height:1.7}.action-row{display:flex;align-items:center;justify-content:space-between;gap:18px;flex-wrap:wrap}.action-row__left,.action-row__right,.directory-list,.topology-summary,.topology-tip-row,.topology-legend,.topology-layout-tools{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.action-field{display:flex;align-items:center;gap:12px}.action-field__label{font-size:14px;color:#b8cae6}.action-meta{margin-top:16px;display:flex;gap:18px;flex-wrap:wrap;color:#8aa3c8;font-size:13px}.directory-root{display:flex;flex-direction:column;gap:8px}.directory-root__value{display:block;padding:12px 14px;border-radius:12px;background:rgba(8,20,35,.92);border:1px solid rgba(84,129,194,.14);color:#dce8ff;word-break:break-all}.directory-list{margin-top:16px}.directory-tag{padding:6px 4px}.topology-panel__header{margin-bottom:12px}.topology-tip-row{font-size:13px;margin-bottom:14px;color:#8aa3c8}.topology-legend{font-size:13px;margin-bottom:14px;color:#a6badb}.topology-layout-tools{margin-bottom:14px}.legend-item{display:inline-flex;align-items:center;gap:8px}.legend-dot{width:10px;height:10px;border-radius:50%;display:inline-block}.legend-dot--success{background:#5dd598;box-shadow:0 0 12px rgba(93,213,152,.45)}.legend-dot--danger{background:#ff7285;box-shadow:0 0 12px rgba(255,114,133,.45)}.legend-line{width:20px;height:2px;display:inline-block;background:#8ea6cb}.legend-line--dashed{background:linear-gradient(90deg,#8ea6cb 50%,transparent 0) repeat-x;background-size:8px 2px}.topology-chart-shell{position:relative;min-height:520px;border-radius:18px;overflow:hidden;background:radial-gradient(circle at top left,rgba(43,124,255,.12),transparent 30%),linear-gradient(180deg,rgba(8,20,35,.82),rgba(6,14,27,.94));border:1px solid rgba(84,129,194,.14)}.topology-chart{width:100%;height:520px}.topology-empty{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;padding:24px;color:#8aa3c8;font-size:14px;line-height:1.8}.topology-detail-card{margin-top:16px;padding:18px 20px}.detail-card__header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:16px}.detail-card__grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.detail-card__item{padding:14px 16px;border-radius:14px;background:rgba(8,20,35,.74);border:1px solid rgba(84,129,194,.12)}.detail-card__item--wide{grid-column:1/-1}.detail-card__value{margin-top:8px;color:#eef5ff;font-size:14px;line-height:1.7;word-break:break-word}.detail-card__value--multiline{display:flex;flex-direction:column;gap:6px}.detail-card__placeholder{color:#8aa3c8;line-height:1.8;font-size:14px}
@media (max-width:992px){.page-banner,.action-row,.topology-summary,.topology-tip-row,.topology-legend,.topology-layout-tools,.detail-card__header{flex-direction:column;align-items:flex-start}.topology-chart-shell,.topology-chart{min-height:460px;height:460px}.detail-card__grid{grid-template-columns:1fr}}
</style>
