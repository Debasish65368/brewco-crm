import { useCallback, useEffect, useState } from "react";
import {
  createCampaign as createCampaignRequest,
  getCampaigns
} from "@/services/campaignsApi";

export function useCampaigns() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await getCampaigns();
      setData(result);
      return result;
    } catch (err) {
      setError(err.message);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  const createCampaign = useCallback(
    async (payload) => {
      const result = await createCampaignRequest(payload);
      await refetch();
      return result;
    },
    [refetch]
  );

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { data, loading, error, refetch, createCampaign };
}
