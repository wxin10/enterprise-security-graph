import http from "@/api/http";

export function fetchRules() {
  return http.get("/api/rules");
}

export function createRule(payload) {
  return http.post("/api/rules", payload);
}

export function updateRule(ruleId, payload) {
  return http.patch(`/api/rules/${ruleId}`, payload);
}

export function grayReleaseRule(ruleId, payload = {}) {
  return http.post(`/api/rules/${ruleId}/gray-release`, payload);
}

export function toggleRuleStatus(ruleId) {
  return http.post(`/api/rules/${ruleId}/toggle-status`);
}
