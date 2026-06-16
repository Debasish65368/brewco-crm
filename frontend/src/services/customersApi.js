import apiClient from "./apiClient";

export function getCustomers(filters = {}) {
  const params = {
    city: filters.city || undefined,
    min_spent: filters.min_spent ?? undefined,
    max_spent: filters.max_spent ?? undefined,
    min_orders: filters.min_orders ?? undefined
  };

  return apiClient
    .get("/customers", { params })
    .then((response) => response.data);
}
