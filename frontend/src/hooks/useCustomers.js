import { useCallback, useEffect, useState } from "react";
import { getCustomers } from "@/services/customersApi";

const DEFAULT_FILTERS = {};

export function useCustomers(filters = DEFAULT_FILTERS) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const city = filters.city;
  const minSpent = filters.min_spent;
  const maxSpent = filters.max_spent;
  const minOrders = filters.min_orders;

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await getCustomers(filters);
      setData(result);
      return result;
    } catch (err) {
      setError(err.message);
      return [];
    } finally {
      setLoading(false);
    }
  }, [city, minSpent, maxSpent, minOrders]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { data, loading, error, refetch };
}
