// 文件路径：frontend/src/api/bans.js
// 作用说明：
// 1. 封装封禁管理相关接口请求。
// 2. 提供列表、详情、放行和重新封禁的统一调用入口。
// 3. 供封禁管理页复用，避免页面组件中散落大量请求细节。
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

export function reblockBan(banId, payload) {
  return http.post(`/api/bans/${banId}/reblock`, payload || {});
}

export function verifyBan(banId) {
  return http.post(`/api/bans/${banId}/verify`);
}
