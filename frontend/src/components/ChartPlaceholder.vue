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
// 2. 先保留浅色可视化占位结构，后续接入 ECharts 时可以原位替换。

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
  color: #1d3147;
}

.chart-placeholder__header span {
  color: #8292a8;
  font-size: 12px;
}

.chart-placeholder__body {
  position: relative;
  margin-top: 18px;
  min-height: 190px;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid rgba(220, 230, 241, 0.92);
  background:
    linear-gradient(180deg, rgba(248, 251, 255, 0.98), rgba(238, 245, 252, 0.95));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.88);
}

.chart-placeholder__grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(116, 145, 185, 0.12) 1px, transparent 1px),
    linear-gradient(90deg, rgba(116, 145, 185, 0.12) 1px, transparent 1px);
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
  color: #203750;
}

.chart-placeholder__sub {
  margin-top: 10px;
  max-width: 420px;
  color: #7c8ea6;
  line-height: 1.7;
  font-size: 13px;
}
</style>
