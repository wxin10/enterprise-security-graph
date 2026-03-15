// 文件路径：frontend/src/api/http.js
// 作用说明：
// 1. 创建 Axios 请求实例。
// 2. 统一配置后端基础地址和超时时间。
// 3. 统一处理接口成功响应、业务错误提示和网络异常提示。

import axios from "axios";
import { ElMessage } from "element-plus";

const http = axios.create({
  // 根据题目要求，这里默认直连已经跑通的 Flask 后端地址。
  baseURL: "http://127.0.0.1:5000",
  timeout: 10000,
  headers: {
    "Content-Type": "application/json"
  }
});

http.interceptors.response.use(
  (response) => {
    const responseData = response.data;

    // 当前后端统一返回结构为：
    // { code, message, data, timestamp }
    // 因此前端这里优先判断业务 code，再决定返回 data 还是抛出异常。
    if (typeof responseData?.code === "number" && responseData.code !== 0) {
      ElMessage.error(responseData.message || "接口请求失败");
      return Promise.reject(new Error(responseData.message || "接口请求失败"));
    }

    return responseData;
  },
  (error) => {
    const errorMessage =
      error?.response?.data?.message ||
      error?.message ||
      "网络异常，请检查后端服务是否已启动";

    ElMessage.error(errorMessage);
    return Promise.reject(error);
  }
);

export default http;
