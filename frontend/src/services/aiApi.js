import apiClient from "./apiClient";

export function suggestSegment(prompt) {
  return apiClient
    .post("/ai/suggest-segment", { prompt })
    .then((response) => response.data);
}

export function draftMessage(goal) {
  return apiClient
    .post("/ai/draft-message", { goal })
    .then((response) => response.data);
}
