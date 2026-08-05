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

export function getDiscoveredSegments() {
  return apiClient.get("/segments/discovered").then((response) => response.data);
}

export function convertClusterToSegment(clusterId, payload) {
  return apiClient.post(`/segments/discovered/${clusterId}/convert`, payload).then((response) => response.data);
}
