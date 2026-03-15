// 文件路径：frontend/src/api/bans.js
// 作用说明：
// 1. 封装封禁管理相关接口请求。
// 2. 统一处理封禁列表查询、详情查询和放行 / 解封操作。
// 3. 供封禁管理页直接复用，避免页面组件中散落大量请求细节。
import http from "@/api/http";

export function fetchBans(params) {
  return http.get("/api/bans", {
    params
  });
}

export function fetchBanDetail(banId) {
  return http.get(`/api/bans/${banId}`);
}

export function unbanBan(banId, payload) {
  return http.post(`/api/bans/${banId}/unban`, payload || {});
}
