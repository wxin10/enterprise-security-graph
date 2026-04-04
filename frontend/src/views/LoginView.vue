<template>
  <!--
    文件路径：frontend/src/views/LoginView.vue
    作用说明：
    1. 提供系统登录页。
    2. 在现有静态登录基础上接入前端模拟角色逻辑。
    3. 登录后根据角色跳转到对应首页，并初始化本地模拟申请数据。
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
          <p>当前版本先采用前端模拟角色登录，优先打通管理员与普通用户的内部运维使用流程。</p>
        </div>

        <el-form :model="formModel" label-position="top" class="login-form">
          <el-form-item label="账号">
            <el-input
              v-model="formModel.username"
              placeholder="请输入账号，例如：admin"
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

          <el-form-item label="登录角色">
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
            进入安全平台
          </el-button>
        </el-form>

        <div class="login-hint">
          演示说明：当前阶段不接后端权限接口。登录时会根据你选择的角色，生成本地模拟用户并写入会话存储。
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// 文件路径：frontend/src/views/LoginView.vue
// 作用说明：
// 1. 提供前端模拟角色登录入口。
// 2. 登录成功后写入统一的用户信息，并根据角色跳转到对应首页。
// 3. 初始化本地模拟申请数据，便于后续普通用户 / 管理员流程演示。

import { computed, onMounted, reactive } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import {
  ROLE_ADMIN,
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
  username: "admin",
  password: "123456",
  role: ROLE_ADMIN
});

const currentRoleDescription = computed(() => {
  const currentRoleOption = LOGIN_ROLE_OPTIONS.find((item) => item.value === formModel.role);
  return currentRoleOption?.description || "";
});

function handleLogin() {
  // 当前阶段采用前端模拟登录。
  // 这里统一调用 auth.js 构造用户对象，并调用 mock-storage 初始化本地处置申请数据。
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
}

.login-page__background {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 20% 20%, rgba(43, 124, 255, 0.26), transparent 24%),
    radial-gradient(circle at 80% 15%, rgba(54, 183, 255, 0.18), transparent 22%),
    radial-gradient(circle at 50% 100%, rgba(19, 61, 130, 0.24), transparent 32%);
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
  color: #f3f8ff;
}

.login-brand__subtitle {
  margin-top: 14px;
  line-height: 1.9;
  color: #94abd0;
  font-size: 15px;
}

.login-panel {
  width: 100%;
  max-width: 460px;
  margin-left: auto;
  padding: 32px;
}

.login-panel__header h1 {
  margin: 0;
  font-size: 28px;
  color: #eff5ff;
}

.login-panel__header p {
  margin: 12px 0 0;
  line-height: 1.8;
  color: #8ea7cb;
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
  color: #8fa7ca;
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
  color: #7389ac;
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
