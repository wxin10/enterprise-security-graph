<template>
  <div class="rule-manage-page app-page">
    <section class="security-panel page-banner">
      <div>
        <h1 class="page-title">规则管理</h1>
        <p class="page-subtitle">
          当前页面用于管理员统一维护识别规则、封禁策略和变更流程，保证普通用户保留研判与申请能力，
          但不直接修改系统关键规则或执行最终高风险动作。
        </p>
      </div>

      <div class="page-banner__actions">
        <el-button v-if="canManageRules" type="primary" plain @click="loadPageData">刷新规则</el-button>
        <el-button v-if="currentUser" type="primary" @click="handleBackHome">返回工作台</el-button>
        <el-button v-else type="primary" @click="handleGoLogin">前往登录</el-button>
      </div>
    </section>

    <el-alert
      v-if="currentUser && !canManageRules"
      title="当前账号不具备规则管理权限，本页只用于说明管理员侧的规则职责边界。"
      type="warning"
      :closable="false"
      show-icon
      class="page-alert"
    />

    <el-row :gutter="18" class="summary-grid">
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">当前身份</div>
          <div class="summary-card__value">{{ currentUser ? currentRoleLabel : "未登录" }}</div>
          <div class="summary-card__hint">只有管理员可进入规则层，普通用户继续聚焦告警分析与申请提交</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">启用规则数</div>
          <div class="summary-card__value summary-card__value--primary">{{ enabledRuleCount }}</div>
          <div class="summary-card__hint">覆盖识别规则与封禁策略，用于演示规则治理入口已补齐</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">识别规则</div>
          <div class="summary-card__value summary-card__value--warning">{{ detectionRuleCount }}</div>
          <div class="summary-card__hint">负责恶意行为识别、异常登录检出和攻击链分析支撑</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">待评估变更</div>
          <div class="summary-card__value summary-card__value--danger">{{ changeQueue.length }}</div>
          <div class="summary-card__hint">突出管理员在规则修改前仍需复核业务影响范围</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="18">
      <el-col :xs="24" :xl="16">
        <section class="security-panel filter-panel">
          <div class="section-header">
            <div>
              <h3>规则筛选</h3>
              <p>支持按规则类型、状态和关键字快速定位，便于展示管理员的规则治理效率。</p>
            </div>
          </div>

          <el-form :inline="true" :model="filterForm" class="filter-form">
            <el-form-item label="规则类型">
              <el-select v-model="filterForm.category" clearable placeholder="全部类型" style="width: 160px">
                <el-option label="识别规则" value="识别规则" />
                <el-option label="封禁规则" value="封禁规则" />
              </el-select>
            </el-form-item>

            <el-form-item label="状态">
              <el-select v-model="filterForm.status" clearable placeholder="全部状态" style="width: 160px">
                <el-option label="启用" value="启用" />
                <el-option label="灰度" value="灰度" />
                <el-option label="停用" value="停用" />
              </el-select>
            </el-form-item>

            <el-form-item label="关键字">
              <el-input
                v-model="filterForm.keyword"
                clearable
                placeholder="输入规则编号 / 名称 / 说明"
                style="width: 280px"
              />
            </el-form-item>
          </el-form>
        </section>

        <section class="security-panel table-panel">
          <div class="section-header">
            <div>
              <h3>规则列表</h3>
              <p>列表聚焦管理员真正能做的事：维护规则阈值、观察命中效果并控制封禁执行条件。</p>
            </div>
            <div class="table-header-tip">当前命中 {{ filteredRules.length }} 条规则</div>
          </div>

          <el-table :data="filteredRules" empty-text="暂无匹配规则">
            <el-table-column prop="rule_code" label="规则编号" min-width="150" />
            <el-table-column prop="rule_name" label="规则名称" min-width="220" show-overflow-tooltip />
            <el-table-column label="类型" min-width="110">
              <template #default="{ row }">
                <el-tag :type="categoryTagType(row.category)" effect="dark">
                  {{ row.category }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" min-width="100">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)" effect="plain">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="threshold" label="触发阈值" min-width="140" />
            <el-table-column prop="hit_count" label="近24小时命中" min-width="130" />
            <el-table-column prop="updated_at" label="最近更新时间" min-width="170" />
            <el-table-column label="操作" min-width="220" fixed="right">
              <template #default="{ row }">
                <div class="table-actions">
                  <el-button link type="primary" @click="handlePreviewRule(row)">查看说明</el-button>
                  <el-button link type="primary" :disabled="!canManageRules" @click="handleGrayRelease(row)">
                    灰度发布
                  </el-button>
                  <el-button link type="danger" :disabled="!canManageRules" @click="handleToggleRule(row)">
                    {{ row.status === "停用" ? "启用规则" : "停用规则" }}
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </el-col>

      <el-col :xs="24" :xl="8">
        <section class="security-panel side-panel">
          <div class="section-header">
            <div>
              <h3>规则变更流程</h3>
              <p>说明管理员页面的核心价值在于规则治理，而不是替代普通用户的日常安全研判工作。</p>
            </div>
          </div>

          <div class="tip-list">
            <div class="tip-item">
              <div class="tip-item__title">1. 分析员提出调整建议</div>
              <div class="tip-item__desc">普通用户可以在告警研判后给出处置意见，但不直接修改规则本身。</div>
            </div>
            <div class="tip-item">
              <div class="tip-item__title">2. 管理员评估影响范围</div>
              <div class="tip-item__desc">结合近 24 小时命中量、误报率和业务影响决定是否灰度发布。</div>
            </div>
            <div class="tip-item">
              <div class="tip-item__title">3. 再执行最终策略</div>
              <div class="tip-item__desc">只有管理员可启停封禁策略和高风险规则，确保关键配置修改可追踪。</div>
            </div>
          </div>
        </section>

        <section class="security-panel side-panel">
          <div class="section-header">
            <div>
              <h3>待评估变更</h3>
              <p>这里展示规则调整待办，让管理员页具备最小演示价值，而不是空白占位。</p>
            </div>
          </div>

          <div v-if="changeQueue.length > 0" class="change-list">
            <div v-for="item in changeQueue" :key="item.id" class="change-card">
              <div class="change-card__header">
                <div class="change-card__title">{{ item.rule_name }}</div>
                <el-tag size="small" :type="statusTagType(item.status)" effect="dark">
                  {{ item.status }}
                </el-tag>
              </div>
              <div class="change-card__meta">建议来源：{{ item.source }}</div>
              <div class="change-card__meta">拟调整内容：{{ item.change_summary }}</div>
              <div class="change-card__meta">提交时间：{{ item.created_at }}</div>
            </div>
          </div>

          <el-empty v-else description="当前没有待评估规则变更" />
        </section>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
// 文件路径：frontend/src/views/RuleManageView.vue
// 作用说明：
// 1. 补齐管理员端“规则管理”页面本体，承接识别规则和封禁策略治理入口。
// 2. 强调普通用户可以做分析与申请，但不能越权修改关键识别规则与封禁策略。
// 3. 当前阶段先以内置模拟规则数据支撑前端演示，不额外改动仓库中的全局数据结构。
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { useRouter } from "vue-router";

import { PERMISSION_KEYS, getCurrentUser, getRoleHomePath, getRoleLabel, hasPermission } from "@/utils/auth";

const RULE_ITEMS = [
  {
    id: "RULE-001",
    rule_code: "DET-LOGIN-01",
    rule_name: "异常登录失败激增识别",
    category: "识别规则",
    status: "启用",
    threshold: "10 分钟内失败次数 >= 15",
    hit_count: 38,
    updated_at: "2026-04-05 00:16:00",
    description: "识别短时间内登录失败次数急剧上升的账号与源 IP 组合。"
  },
  {
    id: "RULE-002",
    rule_code: "DET-LATERAL-02",
    rule_name: "横向移动链路异常扩散识别",
    category: "识别规则",
    status: "灰度",
    threshold: "图谱扩散层级 >= 3 且高危节点数 >= 5",
    hit_count: 12,
    updated_at: "2026-04-04 21:48:00",
    description: "结合 Neo4j 图谱分析结果识别横向移动路径扩散风险。"
  },
  {
    id: "RULE-003",
    rule_code: "BAN-IP-03",
    rule_name: "高危源 IP 自动封禁策略",
    category: "封禁规则",
    status: "启用",
    threshold: "命中 CRITICAL 告警并经管理员审批",
    hit_count: 6,
    updated_at: "2026-04-04 23:36:00",
    description: "管理员审批通过后执行源 IP 封禁，并同步写入封禁台账。"
  },
  {
    id: "RULE-004",
    rule_code: "BAN-ACCOUNT-04",
    rule_name: "异常账号临时冻结策略",
    category: "封禁规则",
    status: "停用",
    threshold: "连续命中 3 次高风险行为",
    hit_count: 0,
    updated_at: "2026-04-03 17:22:00",
    description: "用于冻结高风险账号，当前因误报风险处于停用状态。"
  }
];

const CHANGE_QUEUE_ITEMS = [
  {
    id: "CHG-001",
    rule_name: "横向移动链路异常扩散识别",
    source: "值班分析员处置建议",
    change_summary: "建议提高节点扩散阈值，降低误报率",
    status: "待评估",
    created_at: "2026-04-05 00:05:00"
  },
  {
    id: "CHG-002",
    rule_name: "异常账号临时冻结策略",
    source: "封禁审批复盘",
    change_summary: "建议恢复灰度发布并增加人工确认步骤",
    status: "待评估",
    created_at: "2026-04-04 22:40:00"
  }
];

const router = useRouter();

const currentUser = ref(null);
const ruleItems = ref([]);
const changeQueue = ref([]);

const filterForm = reactive({
  category: "",
  status: "",
  keyword: ""
});

const currentRoleLabel = computed(() => {
  return currentUser.value ? getRoleLabel(currentUser.value.role) : "未登录";
});

const canManageRules = computed(() => {
  return hasPermission(currentUser.value, PERMISSION_KEYS.RULE_MANAGE);
});

const enabledRuleCount = computed(() => {
  return ruleItems.value.filter((item) => item.status === "启用").length;
});

const detectionRuleCount = computed(() => {
  return ruleItems.value.filter((item) => item.category === "识别规则").length;
});

const filteredRules = computed(() => {
  const keyword = String(filterForm.keyword || "").trim().toLowerCase();

  return ruleItems.value.filter((item) => {
    if (filterForm.category && item.category !== filterForm.category) {
      return false;
    }

    if (filterForm.status && item.status !== filterForm.status) {
      return false;
    }

    if (!keyword) {
      return true;
    }

    const haystack = [item.rule_code, item.rule_name, item.description, item.threshold]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return haystack.includes(keyword);
  });
});

function loadPageData() {
  currentUser.value = getCurrentUser();
  ruleItems.value = RULE_ITEMS.map((item) => ({ ...item }));
  changeQueue.value = CHANGE_QUEUE_ITEMS.map((item) => ({ ...item }));
}

function categoryTagType(category) {
  return category === "封禁规则" ? "danger" : "primary";
}

function statusTagType(status) {
  if (status === "启用") {
    return "success";
  }

  if (status === "停用") {
    return "info";
  }

  if (status === "灰度") {
    return "warning";
  }

  return "danger";
}

function handlePreviewRule(row) {
  ElMessage.info(`${row.rule_name}：${row.description}`);
}

function handleGrayRelease(row) {
  if (!canManageRules.value) {
    ElMessage.warning("当前账号不具备规则管理权限");
    return;
  }

  row.status = "灰度";
  ElMessage.success(`${row.rule_name} 已切换为灰度发布状态`);
}

function handleToggleRule(row) {
  if (!canManageRules.value) {
    ElMessage.warning("当前账号不具备规则管理权限");
    return;
  }

  row.status = row.status === "停用" ? "启用" : "停用";
  ElMessage.success(`${row.rule_name} 当前状态已切换为“${row.status}”`);
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
  loadPageData();
});
</script>

<style scoped>
.rule-manage-page {
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

.page-alert {
  margin-top: -4px;
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

.summary-card__value--danger {
  color: #ff6f7d;
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

.table-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
}

.tip-list,
.change-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tip-item,
.change-card {
  padding: 14px;
  border-radius: 16px;
  background: rgba(10, 26, 48, 0.72);
  border: 1px solid rgba(101, 146, 219, 0.12);
}

.tip-item__title,
.change-card__title {
  font-size: 15px;
  font-weight: 700;
  color: #eef5ff;
}

.tip-item__desc,
.change-card__meta {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: #8aa3c8;
}

.change-card__header {
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
