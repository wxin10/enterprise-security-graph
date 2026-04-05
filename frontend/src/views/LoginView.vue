<template>
  <!--
    文件路径：frontend/src/views/LoginView.vue
    作用说明：
    1. 提供系统登录页。
    2. 提供当前版本的控制台登录入口和入口选择。
    3. 登录后根据现有会话状态跳转到对应首页，并初始化本地申请数据。
  -->
  <div class="login-page">
    <div class="login-page__background"></div>

    <div class="login-page__content">
      <div class="login-brand">
        <div class="login-brand__mark">
          <el-icon><Lock /></el-icon>
        </div>
        <div>
          <div class="login-brand__title">企业安全图谱平台</div>
          <div class="login-brand__subtitle">
            基于 Neo4j 的企业网络恶意行为识别与封禁系统
          </div>
        </div>
      </div>

      <div class="login-panel security-panel">
        <div class="login-panel__header">
          <h1>安全控制台登录</h1>
          <p>请使用系统账号进入安全控制台。当前版本提供管理员与普通用户两类控制台入口，登录后将加载对应的菜单与访问范围。</p>
        </div>

        <el-form :model="formModel" label-position="top" class="login-form">
          <el-form-item label="账号">
            <el-input
              v-model="formModel.username"
              placeholder="请输入系统账号"
              size="large"
              clearable
            >
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item label="密码">
            <el-input
              v-model="formModel.password"
              placeholder="请输入密码"
              size="large"
              type="password"
              show-password
              clearable
            >
              <template #prefix>
                <el-icon><Key /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item label="控制台入口">
            <el-radio-group v-model="formModel.role" class="role-selector">
              <el-radio-button
                v-for="item in LOGIN_ROLE_OPTIONS"
                :key="item.value"
                :value="item.value"
              >
                {{ item.label }}
              </el-radio-button>
            </el-radio-group>
            <div class="role-description">
              {{ currentRoleDescription }}
            </div>
          </el-form-item>

          <el-button class="login-button" type="primary" size="large" @click="handleLogin">
            登录并进入控制台
          </el-button>
        </el-form>

        <div class="login-hint">
          登录后系统将按当前控制台会话状态加载菜单与页面访问范围。如需切换入口，请退出后重新登录。
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// 文件路径：frontend/src/views/LoginView.vue
// 作用说明：
// 1. 提供当前版本的控制台登录入口。
// 2. 登录成功后写入统一的会话用户信息，并根据角色跳转到对应首页。
// 3. 初始化本地申请数据，保持控制台流程可运行。

import { computed, onMounted, reactive } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import {
  ROLE_USER,
  LOGIN_ROLE_OPTIONS,
  buildMockUser,
  getCurrentUser,
  getRoleHomePath,
  getRoleLabel,
  saveCurrentUser
} from "@/utils/auth";
import { listDisposalRequests } from "@/utils/mock-storage";

const router = useRouter();

const formModel = reactive({
  username: "",
  password: "",
  role: ROLE_USER
});

const currentRoleDescription = computed(() => {
  const currentRoleOption = LOGIN_ROLE_OPTIONS.find((item) => item.value === formModel.role);
  return currentRoleOption?.description || "";
});

function handleLogin() {
  // 当前版本继续复用现有会话构造逻辑，保证登录页、控制台入口和菜单加载链路保持可运行。
  // 这里同时初始化本地申请数据，避免后续页面首次进入时缺少必要的基础记录。
  if (!String(formModel.username || "").trim()) {
    ElMessage.warning("请输入登录账号");
    return;
  }

  if (!String(formModel.password || "").trim()) {
    ElMessage.warning("请输入登录密码");
    return;
  }

  const currentUser = buildMockUser(formModel);
  saveCurrentUser(currentUser);
  listDisposalRequests();

  ElMessage.success(`${getRoleLabel(currentUser.role)}登录成功，正在进入系统`);
  router.replace(getRoleHomePath(currentUser.role));
}

onMounted(() => {
  const currentUser = getCurrentUser();
  if (currentUser) {
    router.replace(getRoleHomePath(currentUser.role));
  }
});
</script>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  background: linear-gradient(180deg, #f6f8fc 0%, #eef4ff 100%);
}

.login-page__background {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 18% 20%, rgba(43, 124, 255, 0.12), transparent 24%),
    radial-gradient(circle at 82% 14%, rgba(54, 183, 255, 0.1), transparent 20%),
    radial-gradient(circle at 50% 100%, rgba(15, 23, 42, 0.08), transparent 30%);
}

.login-page__content {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  align-items: center;
  padding: 40px 7vw;
  gap: 48px;
}

.login-brand {
  max-width: 520px;
  display: flex;
  align-items: flex-start;
  gap: 18px;
}

.login-brand__mark {
  width: 64px;
  height: 64px;
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 30px;
  color: #ffffff;
  background: linear-gradient(135deg, #2b7cff, #36b7ff);
  box-shadow: 0 20px 42px rgba(43, 124, 255, 0.3);
}

.login-brand__title {
  font-size: 42px;
  font-weight: 800;
  line-height: 1.2;
  color: #0f172a;
}

.login-brand__subtitle {
  margin-top: 14px;
  line-height: 1.9;
  color: #475569;
  font-size: 15px;
}

.login-panel {
  width: 100%;
  max-width: 460px;
  margin-left: auto;
  padding: 32px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: 0 20px 48px rgba(15, 23, 42, 0.08);
}

.login-panel__header h1 {
  margin: 0;
  font-size: 28px;
  color: #0f172a;
}

.login-panel__header p {
  margin: 12px 0 0;
  line-height: 1.8;
  color: #475569;
  font-size: 14px;
}

.login-form {
  margin-top: 26px;
}

.role-selector {
  width: 100%;
}

.role-description {
  margin-top: 12px;
  color: #475569;
  font-size: 12px;
  line-height: 1.7;
}

.login-button {
  width: 100%;
  margin-top: 12px;
  height: 46px;
  font-weight: 700;
  border: none;
  background: linear-gradient(135deg, #2b7cff, #36b7ff);
  box-shadow: 0 18px 28px rgba(43, 124, 255, 0.26);
}

.login-hint {
  margin-top: 18px;
  color: #52637a;
  font-size: 12px;
  line-height: 1.8;
}

@media (max-width: 960px) {
  .login-page__content {
    grid-template-columns: 1fr;
    padding: 28px 20px;
    gap: 24px;
  }

  .login-brand {
    max-width: none;
  }

  .login-brand__title {
    font-size: 30px;
  }

  .login-panel {
    max-width: none;
    margin-left: 0;
  }
}
</style>
