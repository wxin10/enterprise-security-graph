import http from "@/api/http";

export function fetchAuditLogs() {
  return http.get("/api/audit/logs");
}

export function fetchAuditLogDetail(auditId) {
  return http.get(`/api/audit/logs/${auditId}`);
}
