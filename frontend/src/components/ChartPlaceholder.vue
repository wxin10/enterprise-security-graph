<template>
  <!--
    文件路径：frontend/src/components/ChartPlaceholder.vue
    作用说明：
    1. 为后续接入 ECharts 预留图表展示区域。
    2. 当前阶段先提供可视化容器和说明文本，避免一次实现过多复杂图表逻辑。
  -->
  <div class="chart-placeholder security-panel">
    <div class="chart-placeholder__header">
      <h3>{{ title }}</h3>
      <span>{{ subtitle }}</span>
    </div>
    <div class="chart-placeholder__body">
      <div class="chart-placeholder__grid"></div>
      <div class="chart-placeholder__text">
        <div class="chart-placeholder__main">ECharts 图表区域预留</div>
        <div class="chart-placeholder__sub">
          当前轮次先完成页面结构与接口联调，后续可在此接入趋势图、分布图和风险雷达图。
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// 文件路径：frontend/src/components/ChartPlaceholder.vue
// 作用说明：
// 1. 当前不直接渲染复杂图表。
// 2. 先保留深色可视化面板结构，后续接入 ECharts 时可以原位替换。

defineProps({
  title: {
    type: String,
    required: true
  },
  subtitle: {
    type: String,
    default: "图表预留"
  }
});
</script>

<style scoped>
.chart-placeholder {
  padding: 18px;
  min-height: 260px;
}

.chart-placeholder__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.chart-placeholder__header h3 {
  margin: 0;
  font-size: 16px;
  color: #edf4ff;
}

.chart-placeholder__header span {
  color: #7e97bb;
  font-size: 12px;
}

.chart-placeholder__body {
  position: relative;
  margin-top: 18px;
  min-height: 190px;
  border-radius: 16px;
  overflow: hidden;
  background:
    linear-gradient(180deg, rgba(18, 37, 65, 0.9), rgba(9, 19, 34, 0.82));
}

.chart-placeholder__grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(82, 128, 191, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(82, 128, 191, 0.08) 1px, transparent 1px);
  background-size: 28px 28px;
}

.chart-placeholder__text {
  position: relative;
  z-index: 1;
  height: 190px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 16px;
  text-align: center;
}

.chart-placeholder__main {
  font-size: 18px;
  font-weight: 700;
  color: #dbe8ff;
}

.chart-placeholder__sub {
  margin-top: 10px;
  max-width: 420px;
  color: #88a3ca;
  line-height: 1.7;
  font-size: 13px;
}
</style>
