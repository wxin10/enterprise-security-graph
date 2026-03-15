<template>
  <!--
    文件路径：frontend/src/components/AttackChainGraph.vue
    作用说明：
    1. 作为告警页“攻击链图谱”展示组件，专门渲染安全事件语义链。
    2. 使用 ECharts graph 展示攻击源、攻击事件、目标资源、规则、资产、告警和封禁动作之间的关系。
    3. 保持当前项目深蓝安全平台风格，不引入额外大型依赖。
  -->
  <div class="attack-chain-graph">
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
    </div>

    <div class="attack-chain-graph__chart-shell" v-loading="loading">
      <div ref="chartRef" class="attack-chain-graph__chart"></div>

      <div v-if="!loading && (!graphData?.nodes || graphData.nodes.length === 0)" class="attack-chain-graph__empty">
        {{ emptyText }}
      </div>
    </div>
  </div>
</template>

<script setup>
// 文件路径：frontend/src/components/AttackChainGraph.vue
// 作用说明：
// 1. 将后端返回的攻击链 nodes / links 转换为 ECharts graph 所需结构。
// 2. 根据节点类型和攻击链阶段手动布局，突出“攻击源 -> 事件 -> 目标资源 -> 规则/攻击类型 -> 资产 -> 告警 -> 封禁”的语义。
// 3. 支持鼠标悬浮查看实体详情，并在窗口尺寸变化时自动重绘。
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
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

let chartInstance = null;
let resizeHandler = null;

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

function nodeStatusBorder(status) {
  if (["CRITICAL", "HIGH", "FAILED", "DANGER"].includes(status)) {
    return "#ff7285";
  }

  if (["MEDIUM", "WARNING"].includes(status)) {
    return "#ffbf5a";
  }

  if (["LOW", "SUCCESS", "ACTIVE", "BLOCKED", "READY"].includes(status)) {
    return "#67a8ff";
  }

  return "#88a3ca";
}

function shortenText(text, maxLength = 14) {
  if (!text || text.length <= maxLength) {
    return text || "";
  }

  return `${text.slice(0, maxLength - 1)}…`;
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

function calculateNodePositions(nodes) {
  const chartWidth = chartRef.value?.clientWidth || 1100;
  const chartHeight = chartRef.value?.clientHeight || 480;
  const stageRatios = [0.07, 0.22, 0.36, 0.5, 0.64, 0.78, 0.9, 0.98];
  const maxLane = nodes.length ? Math.max(...nodes.map((item) => Number.isFinite(item.lane) ? item.lane : 0)) : 0;
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
    const hasIndependentLane = ["source_ip", "security_event", "request_resource", "attack_type", "target_asset"].includes(
      item.type
    );
    const y = hasIndependentLane
      ? topPadding + ((item.lane || 0) + 0.5) * rowSpacing
      : centerY + ((item.lane || 0) - Math.min(maxLane, 2) / 2) * 72;

    result[item.id] = { x, y };
    return result;
  }, {});
}

function buildChartOption() {
  const nodes = props.graphData?.nodes || [];
  const links = props.graphData?.links || [];
  const positions = calculateNodePositions(nodes);

  const chartNodes = nodes.map((item) => {
    const borderColor = nodeStatusBorder(item.status);
    const isImportant = item.type === "alert" || item.type === "ban_action";

    return {
      ...item,
      ...positions[item.id],
      draggable: false,
      symbolSize: item.symbolSize || (isImportant ? 68 : 56),
      itemStyle: {
        color: nodeTypeColor(item.type),
        borderColor,
        borderWidth: isImportant ? 3 : 2,
        shadowBlur: isImportant ? 26 : 14,
        shadowColor: `${borderColor}55`
      },
      label: {
        show: true,
        color: "#e8f1ff",
        fontSize: 12,
        formatter: shortenText(item.name, isImportant ? 16 : 12)
      }
    };
  });

  const chartLinks = links.map((item) => ({
    ...item,
    lineStyle: {
      color: item.target?.startsWith?.("ban::") ? "#ff9966" : "#5f8fd4",
      width: item.relation === "攻击事件触发告警" || item.relation === "告警联动封禁动作" ? 3 : 2,
      opacity: 0.86,
      curveness: 0.08
    },
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
        layout: "none",
        roam: true,
        focusNodeAdjacency: true,
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: [6, 10],
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

function ensureChart() {
  if (!chartRef.value) {
    return;
  }

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value);
  }
}

function renderChart() {
  const nodes = props.graphData?.nodes || [];
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

.attack-chain-graph__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  color: #a6badb;
  font-size: 13px;
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

@media (max-width: 992px) {
  .attack-chain-graph__legend {
    flex-direction: column;
    align-items: flex-start;
  }

  .attack-chain-graph__chart-shell,
  .attack-chain-graph__chart {
    min-height: 420px;
    height: 420px;
  }
}
</style>
