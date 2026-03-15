// 文件路径：frontend/src/api/alerts.js
// 作用说明：
// 1. 封装告警相关接口请求。
// 2. 统一处理告警列表分页和筛选参数。

import http from "@/api/http";

export function fetchAlerts(params) {
  return http.get("/api/alerts", {
    params
  });
}
