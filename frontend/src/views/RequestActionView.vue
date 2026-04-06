<template>
  <div class="request-page app-page">
    <section class="security-panel page-banner">
      <div>
        <h1 class="page-title">处置申请</h1>
        <p class="page-subtitle">
          用于一线运维和安全分析员填写处置意见并发起申请。普通用户可以提交申请和跟踪状态，最终审批与执行仍由管理员负责。
        </p>
      </div>

      <div class="page-banner__actions">
        <el-button v-if="currentUser" type="primary" plain :loading="loading" @click="loadPageData">刷新状态</el-button>
        <el-button v-if="currentUser" type="primary" @click="handleBackHome">返回工作台</el-button>
        <el-button v-else type="primary" @click="handleGoLogin">前往登录</el-button>
      </div>
    </section>

    <el-row :gutter="18" class="summary-grid">
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">当前角色</div>
          <div class="summary-card__value">{{ currentUser ? currentRoleLabel : "未登录" }}</div>
          <div class="summary-card__hint">普通用户可发起申请，管理员也可提交并跟踪本人的业务处置申请。</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">申请权限</div>
          <div class="summary-card__value summary-card__value--primary">{{ canSubmit ? "已具备" : "不可用" }}</div>
          <div class="summary-card__hint">页面会根据当前登录身份判断是否允许提交处置申请。</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">我的申请数</div>
          <div class="summary-card__value summary-card__value--warning">{{ myRecords.length }}</div>
          <div class="summary-card__hint">可与“我的处理记录”页面联动查看个人申请流转情况。</div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="security-panel summary-card">
          <div class="summary-card__label">待审核数</div>
          <div class="summary-card__value summary-card__value--danger">{{ pendingCount }}</div>
          <div class="summary-card__hint">已提交待管理员审批，尚未执行最终高风险操作。</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="18">
      <el-col :xs="24" :xl="15">
        <section class="security-panel form-panel">
          <div class="section-header">
            <div>
              <h3>申请表单</h3>
              <p>表单字段与处置记录保持一致，提交后可直接进入个人申请流转记录。</p>
            </div>
          </div>

          <el-alert
            v-if="!currentUser"
            title="当前未登录，无法提交处置申请。"
            type="warning"
            :closable="false"
            show-icon
            class="form-alert"
          />

          <el-alert
            v-else-if="!canSubmit"
            title="当前账号不具备处置申请权限，无法提交。"
            type="error"
            :closable="false"
            show-icon
            class="form-alert"
          />

          <el-form ref="formRef" :model="formModel" :rules="formRules" label-width="108px" class="request-form">
            <el-form-item label="告警编号" prop="alert_id">
              <el-input v-model="formModel.alert_id" placeholder="例如 ALT-30021" :disabled="!canSubmit" />
            </el-form-item>

            <el-form-item label="告警名称" prop="alert_name">
              <el-input v-model="formModel.alert_name" placeholder="例如 异常登录行为告警" :disabled="!canSubmit" />
            </el-form-item>

            <el-form-item label="处置目标 IP" prop="source_ip">
              <el-input
                v-model="formModel.source_ip"
                placeholder="例如 10.10.10.25，可选"
                :disabled="!canSubmit"
              />
            </el-form-item>

            <el-form-item label="风险等级" prop="severity">
              <el-select v-model="formModel.severity" placeholder="请选择风险等级" :disabled="!canSubmit">
                <el-option label="LOW" value="LOW" />
                <el-option label="MEDIUM" value="MEDIUM" />
                <el-option label="HIGH" value="HIGH" />
                <el-option label="CRITICAL" value="CRITICAL" />
              </el-select>
            </el-form-item>

            <el-form-item label="处置类型" prop="disposal_type">
              <el-select v-model="formModel.disposal_type" placeholder="请选择处置类型" :disabled="!canSubmit">
                <el-option label="封禁申请" value="封禁申请" />
                <el-option label="隔离申请" value="隔离申请" />
                <el-option label="人工复核申请" value="人工复核申请" />
              </el-select>
            </el-form-item>

            <el-form-item label="紧急程度" prop="urgency_level">
              <el-radio-group v-model="formModel.urgency_level" :disabled="!canSubmit">
                <el-radio-button label="高" />
                <el-radio-button label="中" />
                <el-radio-button label="低" />
              </el-radio-group>
            </el-form-item>

            <el-form-item label="处置意见" prop="disposition_opinion">
              <el-input
                v-model="formModel.disposition_opinion"
                type="textarea"
                :rows="6"
                maxlength="300"
                show-word-limit
                placeholder="请写明研判结论、处置建议和影响范围"
                :disabled="!canSubmit"
              />
            </el-form-item>

            <el-form-item>
              <div class="form-actions">
                <el-button type="primary" :disabled="!canSubmit" :loading="submitting" @click="handleSubmit">提交申请</el-button>
                <el-button :disabled="!canSubmit" @click="handleReset">重置表单</el-button>
              </div>
            </el-form-item>
          </el-form>
        </section>
      </el-col>

      <el-col :xs="24" :xl="9">
        <section class="security-panel side-panel">
          <div class="section-header">
            <div>
              <h3>当前申请人</h3>
              <p>用于确认当前登录人的身份信息，便于核对申请主体所属的运维角色和部门信息。</p>
            </div>
          </div>

          <div v-if="currentUser" class="user-card">
            <div class="user-card__row">
              <span>姓名</span>
              <span>{{ currentUser.display_name }}</span>
            </div>
            <div class="user-card__row">
              <span>账号</span>
              <span>{{ currentUser.username }}</span>
            </div>
            <div class="user-card__row">
              <span>角色</span>
              <span>{{ currentRoleLabel }}</span>
            </div>
            <div class="user-card__row">
              <span>部门</span>
              <span>{{ currentUser.department }}</span>
            </div>
          </div>

          <el-empty v-else description="未登录状态下无法确认申请主体" />
        </section>

        <section class="security-panel side-panel">
          <div class="section-header">
            <div>
              <h3>提交流程说明</h3>
              <p>用于说明“普通用户发起申请、管理员负责审批与执行”的业务边界。</p>
            </div>
          </div>

          <div class="tip-list">
            <div class="tip-item">
              <div class="tip-item__title">1. 记录研判结果</div>
              <div class="tip-item__desc">填写关联告警、风险等级和处置意见，形成可回溯申请单。</div>
            </div>
            <div class="tip-item">
              <div class="tip-item__title">2. 提交待审核</div>
              <div class="tip-item__desc">系统先将申请保存为“待审批”，不会直接执行最终封禁。</div>
            </div>
            <div class="tip-item">
              <div class="tip-item__title">3. 管理员审批</div>
              <div class="tip-item__desc">高权限运维负责人在审批链路中执行最终处理动作。</div>
            </div>
          </div>
        </section>

        <section class="security-panel side-panel">
          <div class="section-header">
            <div>
              <h3>最近提交</h3>
              <p>便于快速回看最近提交的申请及其流转状态。</p>
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
              <div class="record-card__meta">处置目标 IP：{{ item.source_ip || "-" }}</div>
              <div class="record-card__meta">更新时间：{{ item.updated_at || "-" }}</div>
              <div class="record-card__meta">审批备注：{{ item.review_comment || "待管理员审批" }}</div>
              <div class="record-card__meta">联动结果：{{ item.execution_status || "-" }}</div>
            </div>
          </div>

          <el-empty v-else description="当前还没有提交记录" />
        </section>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { useRoute, useRouter } from "vue-router";

import { createDisposal, fetchMyDisposals } from "@/api/disposals";
import { PERMISSION_KEYS, getCurrentUser, getRoleHomePath, getRoleLabel, hasPermission } from "@/utils/auth";

const route = useRoute();
const router = useRouter();

const formRef = ref(null);
const currentUser = ref(null);
const loading = ref(false);
const submitting = ref(false);
const myRecords = ref([]);

const formModel = reactive(createDefaultForm());

const formRules = {
  alert_id: [{ required: true, message: "请输入告警编号", trigger: "blur" }],
  alert_name: [{ required: true, message: "请输入告警名称", trigger: "blur" }],
  severity: [{ required: true, message: "请选择风险等级", trigger: "change" }],
  disposal_type: [{ required: true, message: "请选择处置类型", trigger: "change" }],
  urgency_level: [{ required: true, message: "请选择紧急程度", trigger: "change" }],
  disposition_opinion: [{ required: true, message: "请填写处置意见", trigger: "blur" }]
};

const currentRoleLabel = computed(() => {
  return currentUser.value ? getRoleLabel(currentUser.value.role) : "未登录";
});

const canSubmit = computed(() => {
  return Boolean(currentUser.value) && hasPermission(currentUser.value, PERMISSION_KEYS.DISPOSAL_APPLY);
});

const pendingCount = computed(() => {
  return myRecords.value.filter((item) => String(item.status || "").includes("待")).length;
});

const recentRecords = computed(() => {
  return myRecords.value.slice(0, 3);
});

function createDefaultForm() {
  return {
    alert_id: String(route.query.alert_id || ""),
    alert_name: String(route.query.alert_name || ""),
    source_ip: String(route.query.source_ip || ""),
    severity: String(route.query.severity || "HIGH"),
    disposal_type: String(route.query.disposal_type || "封禁申请"),
    urgency_level: String(route.query.urgency_level || "高"),
    disposition_opinion: String(route.query.disposition_opinion || "")
  };
}

async function loadPageData() {
  currentUser.value = getCurrentUser();

  if (!currentUser.value) {
    myRecords.value = [];
    return;
  }

  loading.value = true;

  try {
    const response = await fetchMyDisposals();
    myRecords.value = response.data?.items || [];
  } finally {
    loading.value = false;
  }
}

function statusTagType(status) {
  if (String(status || "").includes("通过")) {
    return "success";
  }

  if (String(status || "").includes("驳回")) {
    return "danger";
  }

  if (String(status || "").includes("待")) {
    return "warning";
  }

  return "info";
}

async function handleSubmit() {
  if (!canSubmit.value) {
    ElMessage.warning("当前账号暂不具备处置申请权限");
    return;
  }

  await formRef.value?.validate();
  submitting.value = true;

  try {
    const response = await createDisposal({
      alert_id: String(formModel.alert_id || "").trim(),
      alert_name: String(formModel.alert_name || "").trim(),
      source_ip: String(formModel.source_ip || "").trim(),
      severity: formModel.severity,
      disposal_type: formModel.disposal_type,
      urgency_level: formModel.urgency_level,
      disposition_opinion: String(formModel.disposition_opinion || "").trim()
    });

    ElMessage.success(`${response.message}：${response.data?.request_id || ""}`);
    await loadPageData();
    handleReset();
  } finally {
    submitting.value = false;
  }
}

function handleReset() {
  Object.assign(formModel, {
    alert_id: "",
    alert_name: "",
    source_ip: "",
    severity: "HIGH",
    disposal_type: "封禁申请",
    urgency_level: "高",
    disposition_opinion: ""
  });
  formRef.value?.clearValidate();
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
.request-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-banner,
.summary-card,
.form-panel,
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
  color: var(--text-secondary);
}

.summary-card__value {
  margin-top: 12px;
  font-size: 30px;
  font-weight: 700;
  color: var(--text-primary);
}

.summary-card__value--primary,
.summary-card__value--warning,
.summary-card__value--danger {
  color: var(--text-primary);
}

.summary-card__hint {
  margin-top: 10px;
  color: var(--text-secondary);
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
  color: var(--text-primary);
}

.section-header p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.form-alert {
  margin-bottom: 16px;
}

.request-form :deep(.el-select) {
  width: 100%;
}

.form-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.user-card,
.tip-list,
.record-card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.user-card__row,
.tip-item,
.record-card {
  padding: 14px;
  border-radius: 16px;
  background: var(--page-bg-accent);
  border: 1px solid var(--panel-border);
}

.user-card__row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-primary);
  font-size: 14px;
}

.tip-item__title,
.record-card__title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.tip-item__desc,
.record-card__meta {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
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
