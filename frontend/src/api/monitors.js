// 文件路径：frontend/src/api/monitors.js
// 作用说明：
// 1. 统一封装日志监控中心相关接口请求。
// 2. 对接后端监控控制接口，供“日志监控中心”页面直接调用。
// 3. 保持当前项目前端 API 目录风格一致，避免把请求细节散落在页面组件里。
import http from "@/api/http";

export function fetchMonitorStatus() {
  return http.get("/api/monitor/status");
}

export function fetchMonitorConfig() {
  return http.get("/api/monitor/config");
}

export function startMonitor(payload) {
  return http.post("/api/monitor/start", payload || {});
}

export function stopMonitor() {
  return http.post("/api/monitor/stop");
}

