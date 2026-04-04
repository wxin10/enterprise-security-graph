<template>
  <div class="records-page app-page">
    <section class="security-panel page-banner">
      <div>
        <h1 class="page-title">我的处理记录</h1>
        <p class="page-subtitle">
          当前页面面向一线运维 / 值班安全分析员，集中展示本人已发起的处置申请、审批状态和最近流转记录，
          用于支撑告警研判后的个人闭环追踪。
        </p>
      </div>

      <div class="page-banner__actions">
        <el-button type="primary" plain @click="loadRecords">刷新记录</el-button>
        <el-button v-if="currentUser" type="primary" @click="handleBackHome">返回工作台</el-button>
        <el-button v-else type="primary" @click="handleGoLogin">前往登录</el-button>
      </div>
    </section>

    <el-row :gutter="18" class="summary-grid">
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">当前身份</div>
          <div class="summary-card__value">{{ currentUser ? currentRoleLabel : "未登录" }}</div>
          <div class="summary-card__hint">页面默认面向普通用户，但管理员访问时也只展示本人提交记录</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">我的申请总数</div>
          <div class="summary-card__value summary-card__value--primary">{{ records.length }}</div>
          <div class="summary-card__hint">统计当前登录账号已发起的全部处置申请</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">待审核申请</div>
          <div class="summary-card__value summary-card__value--warning">{{ pendingCount }}</div>
          <div class="summary-card__hint">表示已提交给管理员，等待审批或最终执行</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">最近更新时间</div>
          <div class="summary-card__value summary-card__value--small">{{ latestUpdatedAt }}</div>
          <div class="summary-card__hint">用于答辩演示个人处置闭环仍在持续流转</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="18">
      <el-col :xs="24" :xl="16">
        <section class="security-panel filter-panel">
          <div class="section-header">
            <div>
              <h3>筛选条件</h3>
              <p>支持按申请状态、紧急程度和关键字筛选，便于普通用户快速回看自己的处理记录。</p>
            </div>
          </div>

          <el-form :inline="true" :model="filterForm" class="filter-form">
            <el-form-item label="申请状态">
              <el-select v-model="filterForm.status" clearable placeholder="全部状态" style="width: 160px">
                <el-option label="待审核" value="待审核" />
                <el-option label="已通过" value="已通过" />
                <el-option label="已拒绝" value="已拒绝" />
              </el-select>
            </el-form-item>

            <el-form-item label="紧急程度">
              <el-select v-model="filterForm.urgency" clearable placeholder="全部紧急程度" style="width: 160px">
                <el-option label="高" value="高" />
                <el-option label="中" value="中" />
                <el-option label="低" value="低" />
              </el-select>
            </el-form-item>

            <el-form-item label="关键字">
              <el-input
                v-model="filterForm.keyword"
                clearable
                placeholder="输入告警编号 / 告警名称 / 处置意见"
                style="width: 280px"
              />
            </el-form-item>
          </el-form>
        </section>

        <section class="security-panel table-panel">
          <div class="section-header">
            <div>
              <h3>记录列表</h3>
              <p>列表以最近更新时间倒序展示，突出申请编号、风险等级、处置类型和审批状态。</p>
            </div>
            <div class="table-header-tip">当前命中 {{ filteredRecords.length }} 条记录</div>
          </div>

          <el-table :data="filteredRecords" empty-text="当前没有个人处置记录">
            <el-table-column prop="request_id" label="申请编号" min-width="170" />
            <el-table-column prop="alert_id" label="告警编号" min-width="120" />
            <el-table-column prop="alert_name" label="关联告警" min-width="190" show-overflow-tooltip />
            <el-table-column label="风险等级" min-width="110">
              <template #default="{ row }">
                <el-tag :type="severityTagType(row.severity)" effect="dark">
                  {{ row.severity || "-" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="disposal_type" label="处置类型" min-width="120" />
            <el-table-column label="紧急程度" min-width="110">
              <template #default="{ row }">
                <el-tag :type="urgencyTagType(row.urgency_level)" effect="plain">
                  {{ row.urgency_level || "-" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="当前状态" min-width="120">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)" effect="plain">
                  {{ row.status || "-" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="updated_at" label="最近更新时间" min-width="170" />
            <el-table-column prop="disposition_opinion" label="处置意见" min-width="260" show-overflow-tooltip />
          </el-table>
        </section>
      </el-col>

      <el-col :xs="24" :xl="8">
        <section class="security-panel side-panel">
          <div class="section-header">
            <div>
              <h3>个人闭环提示</h3>
              <p>这里强调普通用户的职责边界：可以研判、申请、回看记录，但不能执行最终高风险操作。</p>
            </div>
          </div>

          <div class="tip-list">
            <div class="tip-item">
              <div class="tip-item__title">1. 继续研判</div>
              <div class="tip-item__desc">普通用户可以持续查看告警、图谱分析和详情信息，不是访客角色。</div>
            </div>
            <div class="tip-item">
              <div class="tip-item__title">2. 发起申请</div>
              <div class="tip-item__desc">如需封禁或进一步处置，可填写处置意见并发起申请，等待管理员审批。</div>
            </div>
            <div class="tip-item">
              <div class="tip-item__title">3. 跟踪结果</div>
              <div class="tip-item__desc">在本页面持续跟踪自己的处理记录、审批状态和最新流转时间。</div>
            </div>
          </div>
        </section>

        <section class="security-panel side-panel">
          <div class="section-header">
            <div>
              <h3>最近三条记录</h3>
              <p>便于在答辩时快速展示个人处理闭环，不必每次都阅读整张表。</p>
            </div>
          </div>

          <div v-if="recentRecords.length > 0" class="record-card-list">
            <div v-for="item in recentRecords" :key="item.request_id" class="record-card">
              <div class="record-card__header">
                <div class="record-card__title">{{ item.alert_name }}</div>
                <el-tag size="small" :type="statusTagType(item.status)" effect="dark">
                  {{ item.status }}
                </el-tag>
              </div>
              <div class="record-card__meta">申请编号：{{ item.request_id }}</div>
              <div class="record-card__meta">处置类型：{{ item.disposal_type }}</div>
              <div class="record-card__meta">更新时间：{{ item.updated_at || "-" }}</div>
            </div>
          </div>

          <el-empty v-else description="暂无可展示的最近记录" />
        </section>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
// 文件路径：frontend/src/views/MyRecordsView.vue
// 作用说明：
// 1. 展示当前登录用户本人提交的处置申请和审批状态。
// 2. 强化普通用户是安全分析员而非访客的角色定位。
// 3. 为后续路由接入“我的处理记录”菜单提供页面本体。
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { getCurrentUser, getRoleHomePath, getRoleLabel } from "@/utils/auth";
import { listMyDisposalRequests } from "@/utils/mock-storage";

const router = useRouter();

const currentUser = ref(null);
const records = ref([]);

const filterForm = reactive({
  status: "",
  urgency: "",
  keyword: ""
});

const currentRoleLabel = computed(() => {
  return currentUser.value ? getRoleLabel(currentUser.value.role) : "未登录";
});

const filteredRecords = computed(() => {
  const keyword = String(filterForm.keyword || "").trim().toLowerCase();

  return records.value.filter((item) => {
    if (filterForm.status && item.status !== filterForm.status) {
      return false;
    }

    if (filterForm.urgency && item.urgency_level !== filterForm.urgency) {
      return false;
    }

    if (!keyword) {
      return true;
    }

    const haystack = [item.request_id, item.alert_id, item.alert_name, item.disposition_opinion]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return haystack.includes(keyword);
  });
});

const pendingCount = computed(() => {
  return records.value.filter((item) => String(item.status || "").includes("待")).length;
});

const latestUpdatedAt = computed(() => {
  return records.value[0]?.updated_at || "-";
});

const recentRecords = computed(() => {
  return records.value.slice(0, 3);
});

function loadRecords() {
  currentUser.value = getCurrentUser();
  records.value = currentUser.value ? listMyDisposalRequests(currentUser.value) : [];
}

function statusTagType(status) {
  if (String(status || "").includes("通过")) {
    return "success";
  }

  if (String(status || "").includes("拒绝")) {
    return "danger";
  }

  if (String(status || "").includes("待")) {
    return "warning";
  }

  return "info";
}

function severityTagType(severity) {
  if (severity === "CRITICAL" || severity === "HIGH") {
    return "danger";
  }

  if (severity === "MEDIUM") {
    return "warning";
  }

  return "info";
}

function urgencyTagType(urgency) {
  if (urgency === "高") {
    return "danger";
  }

  if (urgency === "中") {
    return "warning";
  }

  return "info";
}

function handleBackHome() {
  if (!currentUser.value) {
    router.push("/login");
    return;
  }

  router.push(getRoleHomePath(currentUser.value.role));
}

function handleGoLogin() {
  router.push("/login");
}

onMounted(() => {
  loadRecords();
});
</script>

<style scoped>
.records-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-banner,
.summary-card,
.filter-panel,
.table-panel,
.side-panel {
  padding: 20px;
}

.page-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.page-banner__actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.summary-grid :deep(.el-col) {
  margin-bottom: 18px;
}

.summary-card__label {
  font-size: 13px;
  color: #8aa3c8;
}

.summary-card__value {
  margin-top: 12px;
  font-size: 30px;
  font-weight: 700;
  color: #eef5ff;
}

.summary-card__value--primary {
  color: #67a8ff;
}

.summary-card__value--warning {
  color: #ffbf5a;
}

.summary-card__value--small {
  font-size: 16px;
  line-height: 1.6;
  word-break: break-word;
}

.summary-card__hint {
  margin-top: 10px;
  color: #7f98be;
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

.section-header h3 {
  margin: 0;
  font-size: 18px;
  color: #ecf4ff;
}

.section-header p {
  margin: 8px 0 0;
  color: #8aa3c8;
  font-size: 13px;
  line-height: 1.7;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 0;
}

.table-header-tip {
  color: #8fa7ca;
  font-size: 13px;
}

.tip-list,
.record-card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tip-item,
.record-card {
  padding: 14px;
  border-radius: 16px;
  background: rgba(10, 26, 48, 0.72);
  border: 1px solid rgba(101, 146, 219, 0.12);
}

.tip-item__title,
.record-card__title {
  font-size: 15px;
  font-weight: 700;
  color: #eef5ff;
}

.tip-item__desc,
.record-card__meta {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: #8aa3c8;
}

.record-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

@media (max-width: 992px) {
  .page-banner,
  .section-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
