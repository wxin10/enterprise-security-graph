import http from "@/api/http";

export function fetchProfile() {
  return http.get("/api/profile");
}

export function updateProfile(payload) {
  return http.patch("/api/profile", payload);
}
