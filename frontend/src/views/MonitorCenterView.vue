<template>
  <!-- 监控中心页面：展示监控状态、处理结果与流程图联动信息。 -->
  <div class="monitor-page app-page">
    <section class="security-panel page-banner">
      <div>
        <h1 class="page-title">日志监控中心</h1>
        <p class="page-subtitle">
          当前页面集中展示日志接入、检测研判、处置执行与运行状态，便于持续跟踪自动化监控链路。
        </p>
      </div>
      <el-tag :type="monitorStatus.running ? 'success' : 'info'" effect="light" size="large">
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
          <p>统一管理日志监听任务的启动、停止与状态刷新，确保监控任务按设定周期持续执行。</p>
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
          <p>系统按已配置目录持续接入待分析日志文件，并纳入统一监控流程。</p>
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
          <p>展示最近监控批次的检测、告警与处置结果，便于快速跟踪自动化处理状态。</p>
        </div>
        <div class="table-header-tip">记录数：{{ recentRecords.length }}</div>
      </div>
      <el-table :data="recentRecords" v-loading="pageLoading" stripe>
        <el-table-column prop="batch_id" label="批次编号" min-width="200" show-overflow-tooltip />
        <el-table-column prop="source_file" label="原始文件" min-width="280" show-overflow-tooltip />
        <el-table-column label="识别类型" min-width="120">
          <template #default="{ row }">
            <el-tag effect="plain">{{ row.source_type || "-" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="处理状态" min-width="110">
          <template #default="{ row }"><el-tag :type="recordStatusTagType(row.status)" effect="light">{{ row.status || "-" }}</el-tag></template>
        </el-table-column>
        <el-table-column label="检测状态" min-width="120">
          <template #default="{ row }"><el-tag :type="detectionTagType(row.detection_status)" effect="plain">{{ row.detection_status || "-" }}</el-tag></template>
        </el-table-column>
        <el-table-column label="自动封禁 IP" min-width="180">
          <template #default="{ row }">
            <span v-if="!row.auto_blocked_ips || row.auto_blocked_ips.length === 0">-</span>
            <el-space v-else wrap>
              <el-tag v-for="item in row.auto_blocked_ips.slice(0, 2)" :key="item" size="small" effect="light" type="danger">
                {{ item }}
              </el-tag>
            </el-space>
          </template>
        </el-table-column>
        <el-table-column label="自动封禁结果" min-width="150">
          <template #default="{ row }">
            <div class="batch-metric-stack">
              <div>发起 {{ row.auto_block_attempted ?? "-" }}</div>
              <div>成功 {{ row.auto_block_success_count ?? "-" }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="验证 / 拦截" min-width="150">
          <template #default="{ row }">
            <div class="batch-metric-stack">
              <div>验证 {{ row.verification_success_count ?? "-" }}</div>
              <div>拦截 {{ row.truly_blocked_count ?? "-" }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="执行模式 / 主要行为" min-width="170">
          <template #default="{ row }">
            <div class="batch-metric-stack">
              <div>{{ formatBatchEnforcementModeDisplay(row.enforcement_mode) }}</div>
              <div>{{ row.top_auto_block_behavior_type || "-" }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="识别攻击类型" min-width="180">
          <template #default="{ row }">
            <span v-if="!row.detected_attack_types || row.detected_attack_types.length === 0">-</span>
            <el-space v-else wrap>
              <el-tag v-for="item in row.detected_attack_types.slice(0, 2)" :key="item" size="small" effect="plain">{{ item }}</el-tag>
            </el-space>
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
          <p>展示日志接入、解析入库、检测研判、告警联动与处置执行的自动化流程，支持拖拽节点并查看相邻链路。</p>
        </div>
        <div class="topology-summary">
          <el-tag type="success" effect="light">成功链路 {{ topologyData.summary.success_batch_count || 0 }}</el-tag>
          <el-tag type="danger" effect="light">失败链路 {{ topologyData.summary.failed_batch_count || 0 }}</el-tag>
          <el-tag type="warning" effect="light">部分完成 {{ topologyData.summary.partial_batch_count || 0 }}</el-tag>
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
        <span class="legend-item"><i class="legend-line legend-line--dashed"></i>处置执行链路</span>
        <span class="legend-item legend-item--tip">提示：支持拖拽节点、滚轮缩放、点击节点高亮邻接关系</span>
      </div>
      <div class="topology-layout-tools">
        <el-tag size="small" effect="light" :type="topologyLayoutMode === 'force' ? 'warning' : 'success'">
          {{ topologyLayoutMode === "force" ? "自动排布中" : "自由拖动模式" }}
        </el-tag>
        <el-button type="primary" plain size="small" @click="handleTopologyRelayout">重新布局</el-button>
      </div>
      <div class="topology-chart-shell" v-loading="topologyLoading">
        <div ref="topologyChartRef" class="topology-chart"></div>
        <div v-if="!topologyLoading && topologyData.nodes.length === 0" class="topology-empty">当前暂无可展示的监控链路，请先启动监控任务或确认监听目录中存在待处理文件。</div>
      </div>
      <div class="security-panel topology-detail-card">
        <template v-if="selectedTopologyNodeMeta">
          <div class="detail-card__header">
            <div>
              <div class="detail-card__title">{{ selectedTopologyNodeMeta.name }}</div>
              <div class="detail-card__subtitle">{{ selectedTopologyNodeMeta.typeLabel }}</div>
            </div>
            <el-tag effect="light" :type="selectedTopologyNodeMeta.tagType">{{ selectedTopologyNodeMeta.statusText }}</el-tag>
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
        <template v-else><div class="detail-card__placeholder">选中流程图节点后，可查看节点类型、关键属性及其在自动化监控流程中的职责。</div></template>
      </div>
    </section>
  </div>
</template>

<script setup>
// 监控中心页面逻辑：负责监控控制、自动刷新与流程图展示。
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
const latestRecentRecord = computed(() => recentRecords.value?.[0] || {});
const summaryCards = computed(() => [
  { label: "当前状态", value: monitorStatus.running ? "运行中" : "已停止", className: monitorStatus.running ? "summary-card__value--success" : "summary-card__value--muted", hint: "结合任务运行状态与最近心跳信息实时更新" },
  { label: "最近自动封禁 IP", value: latestRecentRecord.value.auto_blocked_ips?.[0] || "-", className: "summary-card__value--danger summary-card__value--small", hint: "展示最近一个处理批次命中的自动处置对象" },
  { label: "自动封禁 / 持续拦截", value: `${latestRecentRecord.value.auto_block_success_count ?? 0} / ${latestRecentRecord.value.truly_blocked_count ?? 0}`, className: "summary-card__value--primary", hint: "反映最近批次的处置执行结果与持续拦截状态" },
  { label: "最近处理时间", value: monitorStatus.latest_processed_at || "-", className: "summary-card__value--warning summary-card__value--small", hint: "用于确认最新监控批次的完成时间" },
  { label: "最近检测状态", value: monitorStatus.latest_detection_status || "IDLE", className: detectionStatusClass.value, hint: "用于快速确认自动检测链路的最新执行结果" }
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
function formatBatchEnforcementModeDisplay(mode) {
  const normalizedMode = String(mode || "").toUpperCase();
  if (normalizedMode === "WINDOWS_FIREWALL" || normalizedMode === "REAL") return "Windows 防火墙";
  if (normalizedMode === "WEB_BLOCKLIST") return "Web 阻断";
  if (normalizedMode === "MOCK") return "策略校验";
  return normalizedMode || "-";
}
function formatBatchEnforcementMode(mode) {
  const normalizedMode = String(mode || "").toUpperCase();
  if (normalizedMode === "WEB_BLOCKLIST") return "Web 阻断";
  if (normalizedMode === "REAL") return "真实执行";
  if (normalizedMode === "MOCK") return "策略校验";
  return normalizedMode || "-";
}
function topologyStatusColor(status) { return status === "FAILED" ? "#ff7285" : status === "PARTIAL" || status === "WARNING" ? "#ffbf5a" : status === "SUCCESS" ? "#5dd598" : status === "ACTIVE" || status === "READY" ? "#67a8ff" : "#7086a8"; }
function topologyTypeColor(type) { return ({ incoming_root: "#2b7cff", watch_directory: "#468df9", log_file: "#33b5ff", adapter: "#25d0b5", neo4j: "#3fd5a1", detection_engine: "#ffb34d", alert: "#ff7a86", ban_action: "#a3b7d7" }[type] || "#6f86ab"); }
function topologyTypeLabel(type) { return ({ incoming_root: "incoming 根目录", watch_directory: "监听子目录", log_file: "处理日志文件", adapter: "日志适配器", neo4j: "Neo4j 图数据库", detection_engine: "检测引擎", alert: "告警节点", ban_action: "处置执行节点" }[type] || "流程节点"); }
function shortenText(text, maxLength = 16) { return !text || text.length <= maxLength ? (text || "") : `${text.slice(0, maxLength - 3)}...`; }
function buildTooltipHtml(title, detailLines) { const lines = Array.isArray(detailLines) ? detailLines.filter(Boolean) : []; return `<div style="min-width:220px;max-width:360px;color:#5b6b80;"><div style="font-size:14px;font-weight:700;color:#243247;">${title}</div>${lines.length ? `<div style="margin-top:6px;line-height:1.7;">${lines.join("<br/>")}</div>` : ""}</div>`; }
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
    return { ...item, ...(rememberedPosition || seedPositions[item.id] || {}), category: categoryIndexMap[item.type] ?? 0, draggable: true, cursor: "move", symbolSize: item.symbolSize || (item.type === "alert" ? 72 : 58), label: { show: true, position: "bottom", distance: 8, color: related ? "#243247" : "rgba(36, 50, 71, 0.38)", fontSize: isSelected ? 13 : 12, formatter: shortenText(item.name, 14) }, itemStyle: { color: topologyTypeColor(item.type), borderColor: topologyStatusColor(item.status), borderWidth: isSelected ? 4 : item.status === "FAILED" ? 3 : 2, shadowBlur: isSelected ? 24 : item.status === "FAILED" || item.status === "SUCCESS" ? 16 : 10, shadowColor: `${topologyStatusColor(item.status)}33`, opacity: related ? 1 : 0.28 } };
  });
  const chartLinks = (topologyData.links || []).map((item) => { const directEdge = isDirectlyConnected(item, selectedId); return { ...item, lineStyle: { color: topologyStatusColor(item.status), width: selectedId ? (directEdge ? 4 : 1.2) : item.highlight ? 4 : 2, opacity: selectedId ? (directEdge ? 0.95 : 0.08) : item.highlight ? 0.95 : 0.72, curveness: item.dashed ? 0.08 : 0.12, type: item.dashed ? "dashed" : "solid" }, label: { show: Boolean(selectedId && directEdge), color: "#6b7a90", fontSize: 11, formatter: item.relation } }; });
  return {
    backgroundColor: "transparent",
    animationDurationUpdate: 450,
    animationEasingUpdate: "quinticInOut",
    legend: { top: 8, textStyle: { color: "#6b7a90" }, itemGap: 16, data: categories.map((item) => item.label) },
    tooltip: { trigger: "item", backgroundColor: "rgba(255, 255, 255, 0.98)", borderColor: "rgba(15, 23, 42, 0.08)", borderWidth: 1, textStyle: { color: "#5b6b80" }, formatter(params) { return params.dataType === "edge" ? buildTooltipHtml(params.data.relation || "链路详情", params.data.detail_lines) : buildTooltipHtml(params.data.name || "节点详情", params.data.detail_lines); } },
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

.summary-card__label,
.directory-root__label,
.table-header-tip,
.detail-card__label {
  font-size: 13px;
  color: var(--text-secondary);
}

.summary-card__value {
  margin-top: 12px;
  font-size: 30px;
  font-weight: 700;
  color: var(--text-primary);
}

.summary-card__value--small {
  font-size: 16px;
  line-height: 1.5;
  word-break: break-word;
}

.summary-card__value--success {
  color: #2f8f68;
}

.summary-card__value--danger {
  color: #d95c6a;
}

.summary-card__value--warning {
  color: #c58b24;
}

.summary-card__value--primary {
  color: #2f7ae5;
}

.summary-card__value--muted {
  color: #7b8798;
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

.section-header h3,
.detail-card__title {
  margin: 0;
  font-size: 18px;
  color: var(--text-primary);
  font-weight: 700;
}

.section-header p,
.detail-card__subtitle,
.legend-item--tip {
  margin: 8px 0 0;
  color: var(--text-secondary);
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
.action-row__right,
.directory-list,
.topology-summary,
.topology-tip-row,
.topology-legend,
.topology-layout-tools {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.action-field {
  display: flex;
  align-items: center;
  gap: 12px;
}

.action-field__label {
  font-size: 14px;
  color: var(--text-secondary);
}

.action-meta {
  margin-top: 16px;
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 13px;
}

.directory-root {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.directory-root__value {
  display: block;
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--page-bg-accent);
  border: 1px solid var(--panel-border);
  color: var(--text-primary);
  word-break: break-all;
}

.directory-list {
  margin-top: 16px;
}

.directory-tag {
  padding: 6px 4px;
}

.batch-metric-stack {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: var(--text-primary);
  font-size: 12px;
  line-height: 1.5;
}

.topology-panel__header {
  margin-bottom: 12px;
}

.topology-tip-row {
  font-size: 13px;
  margin-bottom: 14px;
  color: var(--text-secondary);
}

.topology-legend {
  font-size: 13px;
  margin-bottom: 14px;
  color: var(--text-secondary);
}

.topology-layout-tools {
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
  background: #2f8f68;
  box-shadow: 0 0 10px rgba(47, 143, 104, 0.18);
}

.legend-dot--danger {
  background: #d95c6a;
  box-shadow: 0 0 10px rgba(217, 92, 106, 0.18);
}

.legend-line {
  width: 20px;
  height: 2px;
  display: inline-block;
  background: #9aa7b8;
}

.legend-line--dashed {
  background: linear-gradient(90deg, #9aa7b8 50%, transparent 0) repeat-x;
  background-size: 8px 2px;
}

.topology-chart-shell {
  position: relative;
  min-height: 520px;
  border-radius: 18px;
  overflow: hidden;
  background: linear-gradient(180deg, rgba(43, 124, 255, 0.06), rgba(248, 250, 252, 0.92));
  border: 1px solid var(--panel-border);
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
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.8;
}

.topology-detail-card {
  margin-top: 16px;
  padding: 18px 20px;
}

.detail-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.detail-card__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.detail-card__item {
  padding: 14px 16px;
  border-radius: 14px;
  background: var(--page-bg-accent);
  border: 1px solid var(--panel-border);
}

.detail-card__item--wide {
  grid-column: 1 / -1;
}

.detail-card__value {
  margin-top: 8px;
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
}

.detail-card__value--multiline {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detail-card__placeholder {
  color: var(--text-secondary);
  line-height: 1.8;
  font-size: 14px;
}

@media (max-width: 992px) {
  .page-banner,
  .action-row,
  .topology-summary,
  .topology-tip-row,
  .topology-legend,
  .topology-layout-tools,
  .detail-card__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .topology-chart-shell,
  .topology-chart {
    min-height: 460px;
    height: 460px;
  }

  .detail-card__grid {
    grid-template-columns: 1fr;
  }
}
</style>
