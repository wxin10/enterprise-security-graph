// 文件路径：frontend/src/api/monitors.js
// 作用说明：
// 1. 统一封装日志监控中心相关接口请求。
// 2. 对接后端监控控制、状态查询和拓扑图接口。
// 3. 保持当前前端 API 目录风格一致，避免把请求细节散落在页面组件中。
import http from "@/api/http";

export function fetchMonitorStatus() {
  return http.get("/api/monitor/status");
}

export function fetchMonitorConfig() {
  return http.get("/api/monitor/config");
}

export function fetchMonitorTopology() {
  return http.get("/api/monitor/topology");
}

export function startMonitor(payload) {
  return http.post("/api/monitor/start", payload || {});
}

export function stopMonitor() {
  return http.post("/api/monitor/stop");
}
