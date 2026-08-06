import apiClient from "./apiClient";

export async function getAnalyticsAnswer(question) {
  const response = await apiClient.post("/analytics/query", { question });
  return response.data;
}
