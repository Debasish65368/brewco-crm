import apiClient from "./apiClient";

export function getSegments() {
  return apiClient.get("/segments").then((response) => response.data);
}

export function createSegment(payload) {
  return apiClient.post("/segments", payload).then((response) => response.data);
}

export function deleteSegment(segmentId) {
  return apiClient.delete(`/segments/${segmentId}`).then((response) => response.data);
}
