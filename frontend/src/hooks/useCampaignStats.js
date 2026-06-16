import { useCallback, useEffect, useState } from "react";
import { getCampaignStats } from "@/services/campaignsApi";

export function useCampaignStats(campaignId) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(Boolean(campaignId));
  const [error, setError] = useState(null);

  const refetch = useCallback(async () => {
    if (!campaignId) {
      setData(null);
      setLoading(false);
      setError(null);
      return null;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await getCampaignStats(campaignId);
      setData(result);
      return result;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [campaignId]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { data, loading, error, refetch };
}
