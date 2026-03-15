<template>
  <!--
    文件路径：frontend/src/components/AttackChainGraph.vue
    作用说明：
    1. 作为告警页“攻击链图谱”展示组件，围绕单条告警展示真实攻击链关系。
    2. 使用 ECharts graph + force 力导向布局，提供可拖拽、可缩放、可点击高亮的探索式交互。
    3. 在图谱下方展示当前选中节点的详情卡片，方便答辩时解释攻击链语义。
  -->
  <div class="attack-chain-graph">
    <div class="attack-chain-graph__header">
      <div class="attack-chain-graph__legend">
        <span class="legend-item">
          <i class="legend-dot legend-dot--source"></i>
          攻击源
        </span>
        <span class="legend-item">
          <i class="legend-dot legend-dot--event"></i>
          安全事件
        </span>
        <span class="legend-item">
          <i class="legend-dot legend-dot--alert"></i>
          告警 / 封禁重点高亮
        </span>
        <span class="legend-item legend-item--tip">
          提示：可拖拽节点、滚轮缩放、点击节点查看相邻关系
        </span>
      </div>

      <div class="attack-chain-graph__toolbar">
        <el-tag size="small" effect="dark" :type="layoutMode === 'force' ? 'warning' : 'success'">
          {{ layoutMode === "force" ? "自动排布中" : "自由拖动模式" }}
        </el-tag>
        <el-button type="primary" plain size="small" @click="handleRelayout">
          重新布局
        </el-button>
      </div>
    </div>

    <div class="attack-chain-graph__chart-shell" v-loading="loading">
      <div ref="chartRef" class="attack-chain-graph__chart"></div>

      <div
        v-if="!loading && (!graphData?.nodes || graphData.nodes.length === 0)"
        class="attack-chain-graph__empty"
      >
        {{ emptyText }}
      </div>
    </div>

    <div class="security-panel attack-chain-graph__detail-card">
      <template v-if="selectedNodeMeta">
        <div class="detail-card__header">
          <div>
            <div class="detail-card__title">{{ selectedNodeMeta.name }}</div>
            <div class="detail-card__subtitle">{{ selectedNodeMeta.typeLabel }}</div>
          </div>
          <el-tag effect="dark" :type="selectedNodeMeta.tagType">
            {{ selectedNodeMeta.statusText }}
          </el-tag>
        </div>

        <div class="detail-card__grid">
          <div class="detail-card__item">
            <div class="detail-card__label">节点编号</div>
            <div class="detail-card__value">{{ selectedNodeMeta.id }}</div>
          </div>

          <div class="detail-card__item">
            <div class="detail-card__label">关联关系数</div>
            <div class="detail-card__value">{{ selectedNodeMeta.relatedEdgeCount }}</div>
          </div>

          <div class="detail-card__item detail-card__item--wide">
            <div class="detail-card__label">关键属性</div>
            <div class="detail-card__value detail-card__value--multiline">
              <template v-if="selectedNodeMeta.detailLines.length > 0">
                <div v-for="line in selectedNodeMeta.detailLines" :key="line">{{ line }}</div>
              </template>
              <template v-else>当前节点暂无额外属性说明</template>
            </div>
          </div>
        </div>
      </template>

      <template v-else>
        <div class="detail-card__placeholder">
          点击图谱中的任意节点后，这里会展示节点名称、类型、关键属性和关联关系说明。
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
// 文件路径：frontend/src/components/AttackChainGraph.vue
// 作用说明：
// 1. 将后端返回的攻击链 nodes / links 转换为 ECharts graph 所需结构。
// 2. 通过 force 力导向布局增强图谱的自然分布效果，并保留当前深色安全平台风格。
// 3. 支持节点拖拽、邻接高亮、非相关节点弱化、节点详情卡片和拖拽后位置保留。
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";

const props = defineProps({
  graphData: {
    type: Object,
    default: () => ({
      nodes: [],
      links: []
    })
  },
  loading: {
    type: Boolean,
    default: false
  },
  emptyText: {
    type: String,
    default: "当前告警缺少可展示的攻击链证据。"
  }
});

const chartRef = ref(null);
const selectedNode = ref(null);
const layoutMode = ref("force");

let chartInstance = null;
let resizeHandler = null;
let zrClickHandler = null;
let freezeAfterNextFinished = true;

// 用于保存节点最近一次布局或拖拽后的坐标。
// 这样在抽屉再次刷新或同一条告警重新渲染时，节点不会突然回到初始位置。
const nodePositionState = {};

const selectedNodeMeta = computed(() => {
  if (!selectedNode.value) {
    return null;
  }

  const currentNode = selectedNode.value;
  const relatedEdgeCount = (props.graphData?.links || []).filter((item) => {
    return item.source === currentNode.id || item.target === currentNode.id;
  }).length;

  return {
    id: currentNode.id || "-",
    name: currentNode.name || "未命名节点",
    typeLabel: nodeTypeLabel(currentNode.type),
    statusText: currentNode.status || "NORMAL",
    tagType: statusTagType(currentNode.status),
    relatedEdgeCount,
    detailLines: buildNodeDetailLines(currentNode)
  };
});

function nodeTypeColor(type) {
  const colorMap = {
    source_ip: "#36b7ff",
    security_event: "#2bd2a2",
    request_resource: "#55a8ff",
    attack_type: "#ffb45c",
    rule: "#8d9fe4",
    target_asset: "#7fdb7a",
    alert: "#ff6f7d",
    ban_action: "#ff9966"
  };

  return colorMap[type] || "#6f86ab";
}

function nodeTypeLabel(type) {
  const labelMap = {
    source_ip: "攻击源 IP",
    security_event: "安全事件",
    request_resource: "目标资源",
    attack_type: "攻击类型",
    rule: "命中规则",
    target_asset: "受害主机 / 应用",
    alert: "告警",
    ban_action: "封禁动作"
  };

  return labelMap[type] || "关系节点";
}

function statusTagType(status) {
  if (["CRITICAL", "HIGH", "FAILED", "BLOCKED", "DANGER"].includes(status)) {
    return "danger";
  }

  if (["MEDIUM", "WARNING"].includes(status)) {
    return "warning";
  }

  if (["SUCCESS", "LOW", "ACTIVE", "READY", "RELEASED", "UNBLOCKED", "RESOLVED"].includes(status)) {
    return "success";
  }

  return "info";
}

function nodeStatusBorder(status) {
  if (["CRITICAL", "HIGH", "FAILED", "DANGER", "BLOCKED"].includes(status)) {
    return "#ff7285";
  }

  if (["MEDIUM", "WARNING"].includes(status)) {
    return "#ffbf5a";
  }

  if (["LOW", "SUCCESS", "ACTIVE", "READY", "RELEASED", "UNBLOCKED", "RESOLVED"].includes(status)) {
    return "#67a8ff";
  }

  return "#88a3ca";
}

function shortenText(text, maxLength = 14) {
  if (!text || text.length <= maxLength) {
    return text || "";
  }

  return `${text.slice(0, maxLength - 3)}...`;
}

function buildTooltipHtml(title, detailLines) {
  const lines = Array.isArray(detailLines) ? detailLines.filter(Boolean) : [];
  const detailHtml = lines.length ? `<div style="margin-top:6px;">${lines.join("<br/>")}</div>` : "";

  return `
    <div style="min-width:220px; max-width:360px;">
      <div style="font-size:14px;font-weight:700;color:#eef5ff;">${title}</div>
      ${detailHtml}
    </div>
  `;
}

function buildNodeDetailLines(node) {
  if (Array.isArray(node?.detail_lines) && node.detail_lines.length > 0) {
    return node.detail_lines.filter(Boolean);
  }

  const fallbackLines = [];
  if (node?.type) {
    fallbackLines.push(`节点类型：${nodeTypeLabel(node.type)}`);
  }
  if (node?.status) {
    fallbackLines.push(`当前状态：${node.status}`);
  }

  return fallbackLines;
}

function calculateSeedPositions(nodes) {
  const chartWidth = chartRef.value?.clientWidth || 1100;
  const chartHeight = chartRef.value?.clientHeight || 500;
  const stageRatios = [0.07, 0.22, 0.36, 0.5, 0.64, 0.78, 0.9, 0.98];
  const maxLane = nodes.length
    ? Math.max(...nodes.map((item) => (Number.isFinite(item.lane) ? item.lane : 0)))
    : 0;
  const topPadding = 60;
  const bottomPadding = 60;
  const laneCount = Math.max(maxLane + 1, 1);
  const usableHeight = Math.max(chartHeight - topPadding - bottomPadding, 1);
  const rowSpacing = laneCount > 1 ? usableHeight / laneCount : 0;
  const centerY = chartHeight / 2;

  return nodes.reduce((result, item) => {
    const stageIndex = Number.isFinite(item.stage) ? item.stage : 0;
    const ratio = stageRatios[stageIndex] ?? 0.5;
    const x = Math.round(chartWidth * ratio);
    const hasIndependentLane = [
      "source_ip",
      "security_event",
      "request_resource",
      "attack_type",
      "target_asset"
    ].includes(item.type);
    const y = hasIndependentLane
      ? topPadding + ((item.lane || 0) + 0.5) * rowSpacing
      : centerY + ((item.lane || 0) - Math.min(maxLane, 2) / 2) * 72;

    result[item.id] = { x, y };
    return result;
  }, {});
}

function buildAdjacencyMap(links) {
  const adjacencyMap = new Map();

  links.forEach((item) => {
    if (!adjacencyMap.has(item.source)) {
      adjacencyMap.set(item.source, new Set());
    }
    if (!adjacencyMap.has(item.target)) {
      adjacencyMap.set(item.target, new Set());
    }

    adjacencyMap.get(item.source).add(item.target);
    adjacencyMap.get(item.target).add(item.source);
  });

  return adjacencyMap;
}

function isNodeRelated(nodeId, selectedId, adjacencyMap) {
  if (!selectedId) {
    return true;
  }

  if (nodeId === selectedId) {
    return true;
  }

  return adjacencyMap.get(selectedId)?.has(nodeId) || false;
}

function isDirectlyConnected(link, selectedId) {
  if (!selectedId) {
    return true;
  }

  return link.source === selectedId || link.target === selectedId;
}

function syncSelectedNode() {
  if (!selectedNode.value?.id) {
    return;
  }

  const latestNode = (props.graphData?.nodes || []).find((item) => item.id === selectedNode.value.id);
  if (!latestNode) {
    selectedNode.value = null;
    return;
  }

  selectedNode.value = latestNode;
}

function cleanupNodePositionState() {
  const activeIds = new Set((props.graphData?.nodes || []).map((item) => item.id));
  Object.keys(nodePositionState).forEach((nodeId) => {
    if (!activeIds.has(nodeId)) {
      delete nodePositionState[nodeId];
    }
  });
}

function clearNodePositionState() {
  Object.keys(nodePositionState).forEach((nodeId) => {
    delete nodePositionState[nodeId];
  });
}

function hasStablePositions(nodes) {
  if (!nodes.length) {
    return false;
  }

  return nodes.every((item) => {
    const position = nodePositionState[item.id];
    return position && Number.isFinite(position.x) && Number.isFinite(position.y);
  });
}

function prepareLayoutMode(forceRelayout = false) {
  cleanupNodePositionState();

  const nodes = props.graphData?.nodes || [];
  if (!nodes.length) {
    layoutMode.value = "none";
    freezeAfterNextFinished = false;
    return;
  }

  if (forceRelayout) {
    layoutMode.value = "force";
    freezeAfterNextFinished = true;
    return;
  }

  const canUseFrozenLayout = hasStablePositions(nodes);
  layoutMode.value = canUseFrozenLayout ? "none" : "force";
  freezeAfterNextFinished = !canUseFrozenLayout;
}

function captureNodePositions() {
  if (!chartInstance) {
    return;
  }

  const chartData = chartInstance.getOption()?.series?.[0]?.data || [];
  chartData.forEach((item) => {
    if (item?.id && Number.isFinite(item.x) && Number.isFinite(item.y)) {
      nodePositionState[item.id] = {
        x: item.x,
        y: item.y
      };
    }
  });
}

function handleRelayout() {
  clearNodePositionState();
  prepareLayoutMode(true);
  renderChart({ forceRelayout: true });
}

function buildChartOption() {
  const nodes = props.graphData?.nodes || [];
  const links = props.graphData?.links || [];
  const selectedId = selectedNode.value?.id || "";
  const adjacencyMap = buildAdjacencyMap(links);
  const seedPositions = calculateSeedPositions(nodes);

  const chartNodes = nodes.map((item) => {
    const borderColor = nodeStatusBorder(item.status);
    const isImportant = item.type === "alert" || item.type === "ban_action";
    const isSelected = selectedId === item.id;
    const related = isNodeRelated(item.id, selectedId, adjacencyMap);
    const rememberedPosition = nodePositionState[item.id];

    return {
      ...item,
      ...(rememberedPosition || seedPositions[item.id] || {}),
      draggable: true,
      symbolSize: item.symbolSize || (isImportant ? 68 : 56),
      cursor: "move",
      itemStyle: {
        color: nodeTypeColor(item.type),
        borderColor,
        borderWidth: isSelected ? 4 : isImportant ? 3 : 2,
        shadowBlur: isSelected ? 34 : isImportant ? 26 : 14,
        shadowColor: `${borderColor}66`,
        opacity: related ? 1 : 0.2
      },
      label: {
        show: true,
        position: "bottom",
        distance: 8,
        color: related ? "#e8f1ff" : "rgba(232, 241, 255, 0.32)",
        fontSize: isSelected ? 13 : 12,
        formatter: shortenText(item.name, isImportant ? 16 : 12)
      }
    };
  });

  const chartLinks = links.map((item) => {
    const directEdge = isDirectlyConnected(item, selectedId);
    const highlightEdge =
      item.relation === "攻击事件触发告警" || item.relation === "告警联动封禁动作";

    return {
      ...item,
      lineStyle: {
        color: item.target?.startsWith?.("ban::") ? "#ff9966" : "#5f8fd4",
        width: directEdge && selectedId ? 4 : highlightEdge ? 3 : 2,
        opacity: selectedId ? (directEdge ? 0.96 : 0.08) : 0.82,
        curveness: 0.08
      },
      label: {
        show: Boolean(selectedId && directEdge),
        color: "#8aa3c8",
        fontSize: 11,
        formatter: item.relation
      }
    };
  });

  return {
    backgroundColor: "transparent",
    animationDurationUpdate: 450,
    animationEasingUpdate: "quinticInOut",
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
          return buildTooltipHtml(params.data.relation || "攻击链关系", params.data.detail_lines);
        }

        return buildTooltipHtml(params.data.name || "攻击链节点", params.data.detail_lines);
      }
    },
    series: [
      {
        type: "graph",
        layout: layoutMode.value,
        roam: true,
        draggable: true,
        focusNodeAdjacency: true,
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: [6, 10],
        labelLayout: {
          hideOverlap: true
        },
        ...(layoutMode.value === "force"
          ? {
              force: {
                repulsion: 760,
                gravity: 0.02,
                edgeLength: [150, 280],
                friction: 0.12,
                layoutAnimation: true,
                preventOverlap: true
              }
            }
          : {}),
        scaleLimit: {
          min: 0.45,
          max: 2.2
        },
        data: chartNodes,
        links: chartLinks,
        lineStyle: {
          opacity: 0.85
        },
        emphasis: {
          focus: "adjacency",
          scale: true,
          lineStyle: {
            width: 4
          }
        },
        blur: {
          itemStyle: {
            opacity: 0.12
          },
          lineStyle: {
            opacity: 0.05
          },
          label: {
            opacity: 0.2
          }
        }
      }
    ]
  };
}

function bindChartEvents() {
  if (!chartInstance) {
    return;
  }

  chartInstance.off("click");
  chartInstance.off("finished");
  chartInstance.off("mouseup");

  chartInstance.on("click", (params) => {
    if (params?.dataType === "node") {
      selectedNode.value = params.data;
      renderChart();
    }
  });

  chartInstance.on("finished", () => {
    captureNodePositions();

    if (layoutMode.value === "force" && freezeAfterNextFinished) {
      freezeAfterNextFinished = false;
      layoutMode.value = "none";
      renderChart();
    }
  });

  chartInstance.on("mouseup", () => {
    captureNodePositions();
  });

  if (zrClickHandler) {
    chartInstance.getZr().off("click", zrClickHandler);
  }

  zrClickHandler = (event) => {
    if (!event.target) {
      selectedNode.value = null;
      renderChart();
    }
  };
  chartInstance.getZr().on("click", zrClickHandler);
}

function ensureChart() {
  if (!chartRef.value) {
    return;
  }

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value);
    bindChartEvents();
  }
}

function renderChart(options = {}) {
  const nodes = props.graphData?.nodes || [];
  prepareLayoutMode(options.forceRelayout === true);
  syncSelectedNode();

  if (!chartRef.value || nodes.length === 0) {
    if (chartInstance) {
      chartInstance.clear();
    }
    return;
  }

  ensureChart();
  chartInstance.setOption(buildChartOption(), true);
  chartInstance.resize();
}

watch(
  () => props.graphData,
  async () => {
    await nextTick();
    renderChart();
  },
  { deep: true }
);

watch(
  () => props.loading,
  async (value) => {
    if (!value) {
      await nextTick();
      renderChart();
    }
  }
);

onMounted(async () => {
  await nextTick();
  renderChart();

  resizeHandler = () => {
    if (chartInstance) {
      chartInstance.resize();
    }
  };
  window.addEventListener("resize", resizeHandler);
});

onBeforeUnmount(() => {
  if (resizeHandler) {
    window.removeEventListener("resize", resizeHandler);
    resizeHandler = null;
  }

  if (chartInstance) {
    if (zrClickHandler) {
      chartInstance.getZr().off("click", zrClickHandler);
      zrClickHandler = null;
    }
    chartInstance.dispose();
    chartInstance = null;
  }
});
</script>

<style scoped>
.attack-chain-graph {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.attack-chain-graph__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.attack-chain-graph__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  color: #a6badb;
  font-size: 13px;
}

.attack-chain-graph__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.legend-item--tip {
  color: #8aa3c8;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.legend-dot--source {
  background: #36b7ff;
}

.legend-dot--event {
  background: #2bd2a2;
}

.legend-dot--alert {
  background: #ff6f7d;
}

.attack-chain-graph__chart-shell {
  position: relative;
  min-height: 500px;
  border-radius: 18px;
  overflow: hidden;
  background:
    radial-gradient(circle at top left, rgba(43, 124, 255, 0.12), transparent 28%),
    linear-gradient(180deg, rgba(8, 20, 35, 0.82), rgba(6, 14, 27, 0.95));
  border: 1px solid rgba(84, 129, 194, 0.14);
}

.attack-chain-graph__chart {
  width: 100%;
  height: 500px;
}

.attack-chain-graph__empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: #8aa3c8;
  font-size: 14px;
  line-height: 1.8;
  text-align: center;
}

.attack-chain-graph__detail-card {
  padding: 18px 20px;
}

.detail-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.detail-card__title {
  font-size: 18px;
  font-weight: 700;
  color: #eef5ff;
}

.detail-card__subtitle {
  margin-top: 6px;
  font-size: 13px;
  color: #8aa3c8;
}

.detail-card__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.detail-card__item {
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(8, 20, 35, 0.74);
  border: 1px solid rgba(84, 129, 194, 0.12);
}

.detail-card__item--wide {
  grid-column: 1 / -1;
}

.detail-card__label {
  font-size: 12px;
  color: #8aa3c8;
}

.detail-card__value {
  margin-top: 8px;
  color: #eef5ff;
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
  color: #8aa3c8;
  line-height: 1.8;
  font-size: 14px;
}

@media (max-width: 992px) {
  .attack-chain-graph__header,
  .attack-chain-graph__legend {
    flex-direction: column;
    align-items: flex-start;
  }

  .attack-chain-graph__chart-shell,
  .attack-chain-graph__chart {
    min-height: 420px;
    height: 420px;
  }

  .detail-card__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .detail-card__grid {
    grid-template-columns: 1fr;
  }
}
</style>
