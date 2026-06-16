import apiClient from "./apiClient";

export function getDashboardStats() {
  return apiClient.get("/dashboard/stats").then((response) => response.data);
}
