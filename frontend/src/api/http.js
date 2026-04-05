// 文件路径：frontend/src/api/http.js
// 作用说明：
// 1. 创建 Axios 请求实例。
// 2. 统一配置后端基础地址和超时时间。
// 3. 统一注入控制台会话令牌，并处理接口成功响应、业务错误提示和网络异常提示。

import axios from "axios";
import { ElMessage } from "element-plus";

import { BACKEND_BASE_URL, getSessionToken } from "@/utils/auth";

const http = axios.create({
  // 当前前端继续直连已运行的 Flask 后端服务。
  baseURL: BACKEND_BASE_URL,
  timeout: 10000,
  headers: {
    "Content-Type": "application/json"
  }
});

function shouldShowErrorMessage(config) {
  return !config?.skipErrorMessage && !config?.silentError;
}

http.interceptors.request.use((config) => {
  // 当前控制台登录成功后，会把后端返回的 session_token 保存在 sessionStorage。
  // 这里统一把 token 注入到 Authorization 头中，避免每个 API 文件重复手写。
  const sessionToken = getSessionToken();

  config.headers = config.headers || {};

  if (sessionToken && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${sessionToken}`;
  }

  return config;
});

http.interceptors.response.use(
  (response) => {
    const responseData = response.data;

    // 当前后端统一返回结构为：
    // { code, message, data, timestamp }
    // 因此前端这里优先判断业务 code，再决定返回响应体还是抛出业务异常。
    if (typeof responseData?.code === "number" && responseData.code !== 0) {
      const businessError = new Error(responseData.message || "接口请求失败");
      businessError.response = {
        data: responseData,
        status: response.status
      };
      businessError.config = response.config;

      if (shouldShowErrorMessage(response.config)) {
        ElMessage.error(responseData.message || "接口请求失败");
      }

      return Promise.reject(businessError);
    }

    return responseData;
  },
  (error) => {
    const requestConfig = error?.config;
    const errorMessage =
      error?.response?.data?.message ||
      error?.message ||
      "网络异常，请检查后端服务是否已启动";

    if (shouldShowErrorMessage(requestConfig)) {
      ElMessage.error(errorMessage);
    }

    return Promise.reject(error);
  }
);

export default http;
