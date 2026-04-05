<template>
  <!--
    文件路径：frontend/src/components/StatCard.vue
    作用说明：
    1. 用于统一展示仪表盘的关键指标卡片。
    2. 通过标题、数值、图标和状态色快速呈现安全态势。
  -->
  <div class="stat-card security-panel">
    <div class="stat-card__header">
      <div>
        <div class="stat-card__title">{{ title }}</div>
        <div class="stat-card__hint">{{ hint }}</div>
      </div>
      <div class="stat-card__icon" :class="iconClass">
        <slot name="icon" />
      </div>
    </div>
    <div class="stat-card__value">{{ displayValue }}</div>
  </div>
</template>

<script setup>
// 文件路径：frontend/src/components/StatCard.vue
// 作用说明：
// 1. 抽离仪表盘统计卡片，避免 DashboardView 中重复编写结构。
// 2. 保持样式和交互统一，便于后续继续扩展更多总览指标。

import { computed } from "vue";

const props = defineProps({
  title: {
    type: String,
    required: true
  },
  hint: {
    type: String,
    default: ""
  },
  value: {
    type: [Number, String],
    default: "-"
  },
  tone: {
    type: String,
    default: "primary"
  }
});

// 统一处理空值展示，避免接口尚未返回时页面出现 undefined。
const displayValue = computed(() => {
  return props.value === null || props.value === undefined || props.value === "" ? "-" : props.value;
});

const iconClass = computed(() => `stat-card__icon--${props.tone}`);
</script>

<style scoped>
.stat-card {
  padding: 22px 22px 18px;
  min-height: 148px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.stat-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.stat-card__title {
  color: #6c7f96;
  font-size: 13px;
  letter-spacing: 0.06em;
}

.stat-card__hint {
  margin-top: 10px;
  color: #8a96a8;
  font-size: 12px;
  line-height: 1.6;
}

.stat-card__icon {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: #eef5ff;
}

.stat-card__icon--primary {
  background: linear-gradient(135deg, rgba(43, 124, 255, 0.88), rgba(71, 170, 255, 0.78));
  box-shadow: 0 12px 24px rgba(43, 124, 255, 0.18);
}

.stat-card__icon--danger {
  background: linear-gradient(135deg, rgba(255, 93, 108, 0.88), rgba(255, 149, 102, 0.76));
  box-shadow: 0 12px 24px rgba(255, 108, 120, 0.16);
}

.stat-card__icon--warning {
  background: linear-gradient(135deg, rgba(255, 176, 32, 0.88), rgba(255, 134, 84, 0.78));
  box-shadow: 0 12px 24px rgba(255, 176, 32, 0.16);
}

.stat-card__icon--success {
  background: linear-gradient(135deg, rgba(35, 193, 107, 0.88), rgba(36, 171, 182, 0.74));
  box-shadow: 0 12px 24px rgba(35, 193, 107, 0.16);
}

.stat-card__value {
  margin-top: 20px;
  font-size: 36px;
  font-weight: 700;
  line-height: 1;
  color: #18324d;
}
</style>
