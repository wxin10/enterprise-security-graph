<template>
  <!--
    鏂囦欢璺緞锛歠rontend/src/views/DashboardView.vue
    浣滅敤璇存槑锛?
    1. 灞曠ず浠〃鐩橀椤点€?
    2. 瀵规帴鍚庣 /api/graph/overview 鎺ュ彛銆?
    3. 灞曠ず summary銆乴atest_alerts銆乼op_risk_users銆乼op_risk_ips銆乼op_risk_hosts銆?
  -->
  <div class="dashboard-page app-page">
    <section class="dashboard-hero security-panel">
      <div>
        <h1 class="page-title">浼佷笟缃戠粶瀹夊叏鎬佸娍鎬昏</h1>
        <p class="page-subtitle">
          褰撳墠椤甸潰宸插鎺ュ浘璋辨€昏鎺ュ彛锛岀敤浜庡睍绀哄浘鏁版嵁搴撲腑瀹夊叏瀹炰綋銆佸憡璀︺€佸皝绂佷笌楂橀闄╁璞＄殑鏁翠綋鎬佸娍銆?
        </p>
      </div>

      <el-button type="primary" :loading="loading" @click="loadOverview">
        鍒锋柊鎬昏鏁版嵁
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
            <el-table-column prop="alert_id" label="鍛婅缂栧彿" min-width="100" />
            <el-table-column prop="alert_name" label="鍛婅鍚嶇О" min-width="150" />
            <el-table-column label="涓ラ噸绛夌骇" min-width="110">
              <template #default="{ row }">
                <el-tag :type="severityTagType(row.severity)" effect="light">
                  {{ row.severity || "-" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" min-width="100" />
            <el-table-column prop="score" label="寰楀垎" min-width="80" />
            <el-table-column prop="event_type" label="浜嬩欢绫诲瀷" min-width="120" />
            <el-table-column prop="rule_name" label="鍛戒腑瑙勫垯" min-width="180" show-overflow-tooltip />
          </el-table>
        </div>
      </el-col>

      <el-col :xs="24" :lg="10">
        <div class="security-panel section-panel top-list-panel">
          <div class="section-header">
            <div>
              <h3>高风险对象排行</h3>
              <p>面向首页展示高风险用户、IP 和主机的重点对象。</p>
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
            <div class="risk-block__title">楂橀闄?IP</div>
            <div class="risk-list">
              <div v-for="item in overviewData.top_risk_ips" :key="item.ip_id" class="risk-list__item">
                <div>
                  <div class="risk-list__name">{{ item.ip_address }}</div>
                  <div class="risk-list__meta">{{ item.ip_type || "鏈煡绫诲瀷" }}</div>
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
                  <div class="risk-list__meta">{{ item.asset_type || "鏈煡璧勪骇" }}</div>
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
        <div class="security-panel section-panel chart-panel">
          <div class="section-header">
            <div>
              <h3>鍛婅绛夌骇鍒嗗竷</h3>
              <p>基于 latest_alerts 聚合展示当前首页告警等级结构。</p>
            </div>
          </div>

          <div v-if="alertSeverityChartData.length" class="chart-stack">
            <div v-for="item in alertSeverityChartData" :key="item.key" class="chart-row">
              <div class="chart-row__meta">
                <span class="chart-row__label">{{ item.label }}</span>
                <span class="chart-row__value">{{ item.value }} 条</span>
              </div>
              <div class="chart-row__track">
                <div
                  class="chart-row__fill"
                  :style="{ width: `${item.percent}%`, background: item.color }"
                />
              </div>
              <span class="chart-row__percent">{{ item.percentText }}</span>
            </div>
          </div>
          <el-empty v-else description="鏆傛棤鍛婅绛夌骇鍒嗗竷鏁版嵁" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="12">
        <div class="security-panel section-panel chart-panel">
          <div class="section-header">
            <div>
              <h3>高风险对象分布</h3>
              <p>基于高风险用户、IP 与主机列表聚合展示重点对象占比。</p>
            </div>
          </div>

          <div v-if="riskEntityChartData.length" class="chart-stack">
            <div v-for="item in riskEntityChartData" :key="item.key" class="chart-row">
              <div class="chart-row__meta">
                <span class="chart-row__label">{{ item.label }}</span>
                <span class="chart-row__value">{{ item.value }} 个</span>
              </div>
              <div class="chart-row__track">
                <div
                  class="chart-row__fill"
                  :style="{ width: `${item.percent}%`, background: item.color }"
                />
              </div>
              <span class="chart-row__percent">{{ item.percentText }}</span>
            </div>
          </div>
          <el-empty v-else description="暂无高风险对象分布数据" />
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
// 鏂囦欢璺緞锛歠rontend/src/views/DashboardView.vue
// 浣滅敤璇存槑锛?
// 1. 閫氳繃 fetchGraphOverview 璇诲彇鍚庣鍥捐氨鎬昏鎺ュ彛銆?
// 2. 灏嗘帴鍙ｇ粨鏋滄媶鍒嗕负姒傝鍗＄墖銆佹渶鏂板憡璀﹁〃鍜岄珮椋庨櫓鎺掕涓夐儴鍒嗗睍绀恒€?

import { computed, onMounted, reactive, ref } from "vue";

import { fetchGraphOverview } from "@/api/dashboard";
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

const alertSeverityConfig = {
  CRITICAL: { label: "严重", color: "#dc2626" },
  HIGH: { label: "高危", color: "#f97316" },
  MEDIUM: { label: "中危", color: "#f59e0b" },
  LOW: { label: "低危", color: "#3b82f6" },
  INFO: { label: "提示", color: "#6366f1" },
  UNKNOWN: { label: "未分类", color: "#94a3b8" }
};

const riskEntityConfig = [
  { key: "users", label: "高风险用户", color: "#ef4444", source: "top_risk_users" },
  { key: "ips", label: "高风险 IP", color: "#f97316", source: "top_risk_ips" },
  { key: "hosts", label: "高风险主机", color: "#3b82f6", source: "top_risk_hosts" }
];

function normalizeSeverity(severity) {
  const key = String(severity || "UNKNOWN").toUpperCase();
  return alertSeverityConfig[key] ? key : "UNKNOWN";
}

function formatPercent(value, total) {
  if (!total) {
    return {
      percent: 0,
      percentText: "0%"
    };
  }

  const rawPercent = Number(((value / total) * 100).toFixed(1));

  return {
    percent: rawPercent,
    percentText: `${rawPercent % 1 === 0 ? rawPercent.toFixed(0) : rawPercent}%`
  };
}

const alertSeverityChartData = computed(() => {
  const counts = overviewData.latest_alerts.reduce((accumulator, item) => {
    const key = normalizeSeverity(item?.severity);
    accumulator[key] = (accumulator[key] || 0) + 1;
    return accumulator;
  }, {});
  const total = Object.values(counts).reduce((sum, current) => sum + current, 0);

  return Object.entries(alertSeverityConfig)
    .map(([key, config]) => {
      const value = counts[key] || 0;
      const { percent, percentText } = formatPercent(value, total);

      return {
        key,
        label: config.label,
        color: config.color,
        value,
        percent,
        percentText
      };
    })
    .filter((item) => item.value > 0);
});

const riskEntityChartData = computed(() => {
  const items = riskEntityConfig.map((item) => ({
    key: item.key,
    label: item.label,
    color: item.color,
    value: overviewData[item.source].length
  }));
  const total = items.reduce((sum, item) => sum + item.value, 0);

  return items
    .map((item) => {
      const { percent, percentText } = formatPercent(item.value, total);

      return {
        ...item,
        percent,
        percentText
      };
    })
    .filter((item) => item.value > 0);
});


const summaryCards = computed(() => [
  {
    key: "node_total",
    title: "鍥捐氨鑺傜偣鎬婚噺",
    hint: "褰撳墠 Neo4j 涓墍鏈変笟鍔″疄浣撹妭鐐圭殑鏁伴噺缁熻",
    value: overviewData.summary.node_total,
    tone: "primary",
    icon: "Connection"
  },
  {
    key: "relation_total",
    title: "鍥捐氨鍏崇郴鎬婚噺",
    hint: "褰撳墠鍥捐氨涓殑璁块棶銆佸憡璀︿笌澶勭疆鍏崇郴鏁伴噺",
    value: overviewData.summary.relation_total,
    tone: "success",
    icon: "Share"
  },
  {
    key: "alert_total",
    title: "鍛婅鎬婚噺",
    hint: "褰撳墠鍥炬暟鎹簱涓殑鍛婅鑺傜偣鎬绘暟",
    value: overviewData.summary.alert_total,
    tone: "danger",
    icon: "Bell"
  },
  {
    key: "blocked_ip_total",
    title: "灏佺 IP 鏁伴噺",
    hint: "褰撳墠宸茶灏佺鎴栨爣璁颁负灏佺鐘舵€佺殑 IP 鏁伴噺",
    value: overviewData.summary.blocked_ip_total,
    tone: "warning",
    icon: "Lock"
  },
  {
    key: "high_risk_event_total",
    title: "楂橀闄╀簨浠舵暟",
    hint: "椋庨櫓鍒嗗€煎ぇ浜庣瓑浜?80 鐨勪簨浠舵€绘暟",
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

.chart-panel {
  min-height: 320px;
}

.chart-stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chart-row {
  display: grid;
  grid-template-columns: minmax(92px, 132px) minmax(0, 1fr) 56px;
  align-items: center;
  gap: 12px;
}

.chart-row__meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.chart-row__label {
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
}

.chart-row__value,
.chart-row__percent {
  color: var(--text-secondary);
  font-size: 12px;
}

.chart-row__track {
  height: 12px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(226, 232, 240, 0.92);
}

.chart-row__fill {
  height: 100%;
  min-width: 10px;
  border-radius: inherit;
  box-shadow: 0 8px 18px rgba(59, 130, 246, 0.16);
}

@media (max-width: 992px) {
  .dashboard-hero {
    flex-direction: column;
    align-items: flex-start;
  }

  .chart-row {
    grid-template-columns: 1fr;
  }

  .chart-row__percent {
    justify-self: flex-start;
  }
}
</style>
