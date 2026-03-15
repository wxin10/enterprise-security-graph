// 文件路径：frontend/src/api/dashboard.js
// 作用说明：
// 1. 封装仪表盘相关接口请求。
// 2. 将页面组件与具体 URL 解耦，后续维护时更清晰。

import http from "@/api/http";

export function fetchGraphOverview() {
  return http.get("/api/graph/overview");
}

export function fetchGraphStats() {
  return http.get("/api/graph/stats");
}
