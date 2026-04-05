<template>
  <!--
    文件路径：frontend/src/views/DashboardView.vue
    作用说明：
    1. 展示仪表盘首页。
    2. 对接后端 /api/graph/overview 接口。
    3. 展示 summary、latest_alerts、top_risk_users、top_risk_ips、top_risk_hosts。
  -->
  <div class="dashboard-page app-page">
    <section class="dashboard-hero security-panel">
      <div>
        <h1 class="page-title">企业网络安全态势总览</h1>
        <p class="page-subtitle">
          当前页面已对接图谱总览接口，用于展示图数据库中安全实体、告警、封禁与高风险对象的整体态势。
        </p>
      </div>

      <el-button type="primary" :loading="loading" @click="loadOverview">
        刷新总览数据
      </el-button>
    </section>

    <el-row :gutter="18" class="summary-grid">
      <el-col :xs="24" :sm="12" :lg="8" :xl="6" v-for="item in summaryCards" :key="item.key">
        <StatCard :title="item.title" :hint="item.hint" :value="item.value" :tone="item.tone">
          <template #icon>
            <component :is="item.icon" />
          </template>
        </StatCard>
      </el-col>
    </el-row>

    <el-row :gutter="18" class="overview-section">
      <el-col :xs="24" :lg="14">
        <div class="security-panel section-panel">
          <div class="section-header">
            <div>
              <h3>最新告警动态</h3>
              <p>展示 overview 接口中的 latest_alerts 数据，用于首页快速研判。</p>
            </div>
          </div>

          <el-table :data="overviewData.latest_alerts" v-loading="loading" stripe>
            <el-table-column prop="alert_id" label="告警编号" min-width="100" />
            <el-table-column prop="alert_name" label="告警名称" min-width="150" />
            <el-table-column label="严重等级" min-width="110">
              <template #default="{ row }">
                <el-tag :type="severityTagType(row.severity)" effect="light">
                  {{ row.severity || "-" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" min-width="100" />
            <el-table-column prop="score" label="得分" min-width="80" />
            <el-table-column prop="event_type" label="事件类型" min-width="120" />
            <el-table-column prop="rule_name" label="命中规则" min-width="180" show-overflow-tooltip />
          </el-table>
        </div>
      </el-col>

      <el-col :xs="24" :lg="10">
        <div class="security-panel section-panel top-list-panel">
          <div class="section-header">
            <div>
              <h3>高风险对象排行</h3>
              <p>面向论文展示高风险用户、IP 和主机的重点对象。</p>
            </div>
          </div>

          <div class="risk-block">
            <div class="risk-block__title">高风险用户</div>
            <div class="risk-list">
              <div v-for="item in overviewData.top_risk_users" :key="item.user_id" class="risk-list__item">
                <div>
                  <div class="risk-list__name">{{ item.username }}</div>
                  <div class="risk-list__meta">{{ item.department || "未标记部门" }}</div>
                </div>
                <el-tag type="danger" effect="light">{{ item.risk_score ?? "-" }}</el-tag>
              </div>
            </div>
          </div>

          <div class="risk-block">
            <div class="risk-block__title">高风险 IP</div>
            <div class="risk-list">
              <div v-for="item in overviewData.top_risk_ips" :key="item.ip_id" class="risk-list__item">
                <div>
                  <div class="risk-list__name">{{ item.ip_address }}</div>
                  <div class="risk-list__meta">{{ item.ip_type || "未知类型" }}</div>
                </div>
                <el-tag :type="item.is_blocked ? 'danger' : 'warning'" effect="light">
                  {{ item.risk_score ?? "-" }}
                </el-tag>
              </div>
            </div>
          </div>

          <div class="risk-block">
            <div class="risk-block__title">高风险主机</div>
            <div class="risk-list">
              <div v-for="item in overviewData.top_risk_hosts" :key="item.host_id" class="risk-list__item">
                <div>
                  <div class="risk-list__name">{{ item.hostname }}</div>
                  <div class="risk-list__meta">{{ item.asset_type || "未知资产" }}</div>
                </div>
                <el-tag type="warning" effect="light">{{ item.risk_score ?? "-" }}</el-tag>
              </div>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="18" class="charts-section">
      <el-col :xs="24" :lg="12">
        <ChartPlaceholder title="告警等级趋势分析" subtitle="ECharts 预留区" />
      </el-col>
      <el-col :xs="24" :lg="12">
        <ChartPlaceholder title="高风险实体分布" subtitle="ECharts 预留区" />
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
// 文件路径：frontend/src/views/DashboardView.vue
// 作用说明：
// 1. 通过 fetchGraphOverview 读取后端图谱总览接口。
// 2. 将接口结果拆分为概览卡片、最新告警表和高风险排行三部分展示。

import { computed, onMounted, reactive, ref } from "vue";

import { fetchGraphOverview } from "@/api/dashboard";
import ChartPlaceholder from "@/components/ChartPlaceholder.vue";
import StatCard from "@/components/StatCard.vue";

const loading = ref(false);

const overviewData = reactive({
  summary: {},
  latest_alerts: [],
  top_risk_users: [],
  top_risk_ips: [],
  top_risk_hosts: []
});

function severityTagType(severity) {
  if (severity === "CRITICAL" || severity === "HIGH") {
    return "danger";
  }
  if (severity === "MEDIUM") {
    return "warning";
  }
  return "info";
}

async function loadOverview() {
  loading.value = true;

  try {
    const response = await fetchGraphOverview();
    const data = response?.data || {};

    overviewData.summary = data.summary || {};
    overviewData.latest_alerts = data.latest_alerts || [];
    overviewData.top_risk_users = data.top_risk_users || [];
    overviewData.top_risk_ips = data.top_risk_ips || [];
    overviewData.top_risk_hosts = data.top_risk_hosts || [];
  } finally {
    loading.value = false;
  }
}

const summaryCards = computed(() => [
  {
    key: "node_total",
    title: "图谱节点总量",
    hint: "当前 Neo4j 中所有业务实体节点数量",
    value: overviewData.summary.node_total,
    tone: "primary",
    icon: "Connection"
  },
  {
    key: "relation_total",
    title: "图谱关系总量",
    hint: "当前图谱中的访问、告警与处置关系数量",
    value: overviewData.summary.relation_total,
    tone: "success",
    icon: "Share"
  },
  {
    key: "alert_total",
    title: "告警总量",
    hint: "当前图数据库中的告警节点总数",
    value: overviewData.summary.alert_total,
    tone: "danger",
    icon: "Bell"
  },
  {
    key: "blocked_ip_total",
    title: "封禁 IP 数量",
    hint: "已被联动封禁或标记为封禁状态的 IP 数量",
    value: overviewData.summary.blocked_ip_total,
    tone: "warning",
    icon: "Lock"
  },
  {
    key: "high_risk_event_total",
    title: "高风险事件数",
    hint: "风险分值大于等于 80 的事件总数",
    value: overviewData.summary.high_risk_event_total,
    tone: "danger",
    icon: "Warning"
  }
]);

onMounted(() => {
  loadOverview();
});
</script>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.dashboard-hero {
  padding: 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(237, 244, 255, 0.92));
}

.summary-grid {
  margin-top: 0;
}

.summary-grid :deep(.el-col) {
  margin-bottom: 18px;
}

.overview-section,
.charts-section {
  margin-top: 0;
}

.section-panel {
  padding: 18px;
  min-height: 420px;
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

.top-list-panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.risk-block__title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.risk-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.risk-list__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.98), rgba(255, 255, 255, 0.94));
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.76);
}

.risk-list__name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.risk-list__meta {
  margin-top: 5px;
  color: var(--text-secondary);
  font-size: 12px;
}

:deep(.stat-card__title) {
  color: var(--text-secondary) !important;
}

:deep(.stat-card__hint) {
  color: var(--text-secondary) !important;
}

:deep(.stat-card__value) {
  color: var(--text-primary) !important;
}

:deep(.chart-placeholder__header h3) {
  color: var(--text-primary) !important;
}

:deep(.chart-placeholder__header span) {
  color: var(--text-secondary) !important;
}

:deep(.chart-placeholder__body) {
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.96), rgba(237, 244, 255, 0.94)) !important;
  border: 1px dashed rgba(148, 163, 184, 0.24);
}

:deep(.chart-placeholder__grid) {
  background-image:
    linear-gradient(rgba(148, 163, 184, 0.16) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.16) 1px, transparent 1px) !important;
}

:deep(.chart-placeholder__main) {
  color: var(--text-primary) !important;
}

:deep(.chart-placeholder__sub) {
  color: var(--text-secondary) !important;
}

@media (max-width: 992px) {
  .dashboard-hero {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
