import http from "@/api/http";

export function fetchDisposals() {
  return http.get("/api/disposals");
}

export function createDisposal(payload) {
  return http.post("/api/disposals", payload);
}

export function fetchMyDisposals() {
  return http.get("/api/disposals/my");
}

export function updateDisposal(requestId, payload) {
  return http.patch(`/api/disposals/${requestId}`, payload);
}
