<template>
  <!-- 工作台总览页面：展示图谱概况、最新告警与高风险对象。 -->
  <div class="dashboard-page app-page">
    <section class="dashboard-hero security-panel">
      <div>
        <h1 class="page-title">企业网络安全态势总览</h1>
        <p class="page-subtitle">
          汇总图谱规模、最新告警、高风险对象和关键指标，支撑安全运营人员进行快速研判。
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

    <el-row v-if="canViewApprovalOverview" :gutter="18" class="summary-grid">
      <el-col :xs="24" :sm="12" :lg="8" :xl="6" v-for="item in approvalCards" :key="item.key">
        <StatCard :title="item.title" :hint="item.hint" :value="item.value" :tone="item.tone">
          <template #icon>
            <component :is="item.icon" />
          </template>
        </StatCard>
      </el-col>
    </el-row>

    <el-row v-if="canViewApprovalOverview" :gutter="18" class="approval-section">
      <el-col :xs="24" :lg="14">
        <div class="security-panel section-panel approval-panel">
          <div class="section-header">
            <div>
              <h3>待审批申请</h3>
              <p>首页汇总最近待审批的处置申请，支持直接执行审批动作或进入封禁审批页面继续处理。</p>
            </div>
            <div class="section-actions">
              <div class="table-header-tip">最近审批时间：{{ latestApprovalActionText }}</div>
              <el-button plain @click="handleOpenApprovalPage">进入审批页</el-button>
            </div>
          </div>

          <el-table :data="pendingDisposals" v-loading="loading" empty-text="当前没有待审批申请" stripe>
            <el-table-column prop="request_id" label="申请编号" min-width="170" />
            <el-table-column prop="disposal_type" label="申请类型" min-width="120" />
            <el-table-column prop="applicant_name" label="申请人" min-width="120" />
            <el-table-column prop="source_ip" label="处置目标 IP" min-width="140" />
            <el-table-column prop="created_at" label="提交时间" min-width="170" />
            <el-table-column label="当前状态" min-width="110">
              <template #default="{ row }">
                <el-tag :type="approvalStatusTagType(row.status)" effect="plain">
                  {{ row.status || "-" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <div class="action-buttons">
                  <el-button
                    type="primary"
                    link
                    :loading="isApprovalActionLoading(row.request_id)"
                    @click="handleApproval(row, '已通过')"
                  >
                    通过
                  </el-button>
                  <el-button
                    type="danger"
                    link
                    :loading="isApprovalActionLoading(row.request_id)"
                    @click="handleApproval(row, '已驳回')"
                  >
                    驳回
                  </el-button>
                  <el-button type="primary" link @click="handleOpenApprovalPage">审批页</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>

      <el-col :xs="24" :lg="10">
        <div class="security-panel section-panel review-panel">
          <div class="section-header">
            <div>
              <h3>最近审批记录</h3>
              <p>集中呈现最近已通过、已驳回和联动执行结果，便于首页快速回看审批闭环。</p>
            </div>
          </div>

          <div v-if="recentReviews.length" class="review-card-list">
            <div v-for="item in recentReviews" :key="`${item.request_id}-${item.reviewed_at || item.updated_at}`" class="review-card">
              <div class="review-card__header">
                <div class="review-card__title">{{ item.alert_name }}</div>
                <el-tag size="small" :type="approvalStatusTagType(item.status)" effect="dark">
                  {{ item.status }}
                </el-tag>
              </div>
              <div class="review-card__meta">申请编号：{{ item.request_id }}</div>
              <div class="review-card__meta">申请类型：{{ item.disposal_type }}</div>
              <div class="review-card__meta">审批人：{{ item.reviewer_name || "-" }}</div>
              <div class="review-card__meta">审批时间：{{ item.reviewed_at || item.updated_at || "-" }}</div>
              <div class="review-card__meta">审批备注：{{ item.review_comment || "-" }}</div>
              <div class="review-card__meta" v-if="item.execution_status">联动结果：{{ item.execution_status }}</div>
            </div>
          </div>
          <el-empty v-else description="当前没有最近审批记录" />
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="18" class="overview-section">
      <el-col :xs="24" :lg="14">
        <div class="security-panel section-panel">
          <div class="section-header">
            <div>
              <h3>最新告警动态</h3>
              <p>展示最新告警记录，便于首页快速识别当前高风险事件。</p>
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
              <p>聚合展示高风险用户、IP 和主机，便于快速锁定重点处置对象。</p>
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
        <div class="security-panel section-panel chart-panel">
          <div class="section-header">
            <div>
              <h3>告警等级分布</h3>
              <p>基于最新告警记录聚合当前等级结构，便于查看风险集中区间。</p>
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
          <el-empty v-else description="暂无告警等级分布数据" />
        </div>
      </el-col>

      <el-col :xs="24" :lg="12">
        <div class="security-panel section-panel chart-panel">
          <div class="section-header">
            <div>
              <h3>高风险对象分布</h3>
              <p>聚合高风险用户、IP 与主机数量，辅助判断风险暴露重点。</p>
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
// 工作台总览页面逻辑：读取图谱概况并组织首页展示数据。
import { computed, onMounted, reactive, ref } from "vue";

import { fetchGraphOverview } from "@/api/dashboard";
import { updateDisposal } from "@/api/disposals";
import StatCard from "@/components/StatCard.vue";
import { PERMISSION_KEYS, getCurrentUser, hasPermission } from "@/utils/auth";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRouter } from "vue-router";

const router = useRouter();
const loading = ref(false);
const currentUser = ref(null);
const approvalActionLoadingMap = reactive({});

const overviewData = reactive({
  summary: {},
  latest_alerts: [],
  top_risk_users: [],
  top_risk_ips: [],
  top_risk_hosts: [],
  approval_overview: {}
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

function approvalStatusTagType(status) {
  if (status === "已通过") {
    return "success";
  }

  if (status === "已驳回") {
    return "danger";
  }

  return "warning";
}

function isApprovalActionLoading(requestId) {
  return Boolean(approvalActionLoadingMap[requestId]);
}

async function loadOverview() {
  currentUser.value = getCurrentUser();
  loading.value = true;

  try {
    const response = await fetchGraphOverview();
    const data = response?.data || {};

    overviewData.summary = data.summary || {};
    overviewData.latest_alerts = data.latest_alerts || [];
    overviewData.top_risk_users = data.top_risk_users || [];
    overviewData.top_risk_ips = data.top_risk_ips || [];
    overviewData.top_risk_hosts = data.top_risk_hosts || [];
    overviewData.approval_overview = data.approval_overview || {};
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

const canViewApprovalOverview = computed(() => {
  return hasPermission(currentUser.value, PERMISSION_KEYS.BAN_EXECUTE);
});

const pendingDisposals = computed(() => {
  return overviewData.approval_overview?.recent_disposals || [];
});

const recentReviews = computed(() => {
  return overviewData.approval_overview?.recent_reviews || [];
});

const latestApprovalActionText = computed(() => {
  return overviewData.approval_overview?.recent_action_time || "暂无审批动作";
});

const summaryCards = computed(() => [
  {
    key: "node_total",
    title: "图谱节点总量",
    hint: "统计当前图谱中的业务实体与安全对象节点数量",
    value: overviewData.summary.node_total,
    tone: "primary",
    icon: "Connection"
  },
  {
    key: "relation_total",
    title: "图谱关系总量",
    hint: "展示访问、告警、处置等关联关系规模",
    value: overviewData.summary.relation_total,
    tone: "success",
    icon: "Share"
  },
  {
    key: "alert_total",
    title: "告警总量",
    hint: "展示当前图谱中的告警记录数量",
    value: overviewData.summary.alert_total,
    tone: "danger",
    icon: "Bell"
  },
  {
    key: "blocked_ip_total",
    title: "封禁 IP 数量",
    hint: "统计当前处于封禁状态的风险源 IP 数量",
    value: overviewData.summary.blocked_ip_total,
    tone: "warning",
    icon: "Lock"
  },
  {
    key: "high_risk_event_total",
    title: "高风险事件数",
    hint: "统计风险分值达到高危阈值的事件数量",
    value: overviewData.summary.high_risk_event_total,
    tone: "danger",
    icon: "Warning"
  }
]);

const approvalCards = computed(() => [
  {
    key: "pending_disposal_count",
    title: "待审批申请数",
    hint: "汇总当前仍待管理员处理的处置申请数量。",
    value: overviewData.approval_overview?.pending_disposal_count,
    tone: "warning",
    icon: "DocumentCopy"
  },
  {
    key: "approved_today_count",
    title: "今日已通过数",
    hint: "统计今日已完成审批通过的处置申请数量。",
    value: overviewData.approval_overview?.approved_today_count,
    tone: "success",
    icon: "CircleCheck"
  },
  {
    key: "rejected_today_count",
    title: "今日已驳回数",
    hint: "统计今日已驳回的处置申请数量。",
    value: overviewData.approval_overview?.rejected_today_count,
    tone: "danger",
    icon: "CircleClose"
  },
  {
    key: "recent_action_time",
    title: "最近审批时间",
    hint: "用于确认审批链路是否保持实时更新。",
    value: latestApprovalActionText.value,
    tone: "primary",
    icon: "Timer"
  }
]);

async function handleApproval(row, status) {
  const isApprove = status === "已通过";
  const defaultComment = isApprove ? "同意按申请意见执行处置动作" : "驳回当前申请，请补充完整研判依据";

  try {
    const promptResult = await ElMessageBox.prompt(
      `请填写申请 ${row.request_id} 的审批备注。`,
      isApprove ? "审批通过" : "审批驳回",
      {
        confirmButtonText: isApprove ? "确认通过" : "确认驳回",
        cancelButtonText: "取消",
        inputType: "textarea",
        inputValue: defaultComment,
        inputPlaceholder: "请输入审批备注"
      }
    );

    approvalActionLoadingMap[row.request_id] = true;
    const response = await updateDisposal(row.request_id, {
      status,
      review_comment: promptResult.value || defaultComment
    });

    ElMessage.success(response?.message || (isApprove ? "审批通过成功" : "审批驳回成功"));
    await loadOverview();
  } catch (error) {
    if (
      error === "cancel" ||
      error === "close" ||
      error?.action === "cancel" ||
      error?.action === "close"
    ) {
      return;
    }
  } finally {
    approvalActionLoadingMap[row.request_id] = false;
  }
}

function handleOpenApprovalPage() {
  router.push("/console/bans");
}

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
.charts-section,
.approval-section {
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

.section-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
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

.approval-panel,
.review-panel {
  min-height: 100%;
}

.review-card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.review-card {
  padding: 14px 16px;
  border-radius: 16px;
  background: var(--page-bg-accent);
  border: 1px solid var(--panel-border);
}

.review-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.review-card__title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.review-card__meta,
.table-header-tip {
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
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
