import apiClient from "./apiClient";

export function getCampaigns() {
  return apiClient.get("/campaigns").then((response) => response.data);
}

export function createCampaign(payload) {
  return apiClient
    .post("/campaigns", payload)
    .then((response) => response.data);
}

export function getCampaignStats(campaignId) {
  return apiClient
    .get(`/campaigns/${campaignId}/stats`)
    .then((response) => response.data);
}
