import http from "@/api/http";

export function fetchUsers() {
  return http.get("/api/users");
}

export function createUser(payload) {
  return http.post("/api/users", payload);
}

export function updateUser(userId, payload) {
  return http.patch(`/api/users/${userId}`, payload);
}

export function resetUserPassword(userId) {
  return http.post(`/api/users/${userId}/reset-password`);
}

export function toggleUserStatus(userId) {
  return http.post(`/api/users/${userId}/toggle-status`);
}
