import apiClient from "./apiClient";

export function getDashboardStats() {
  return apiClient.get("/dashboard/stats").then((response) => response.data);
}

export function getRevenueTrend() {
  return apiClient.get("/dashboard/revenue-trend").then((response) => response.data);
}