import { useCallback, useEffect, useState } from "react";
import {
  getDiscoveredSegments,
  convertClusterToSegment
} from "@/services/segmentsApi";

export function useDiscoveredSegments() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [convertingId, setConvertingId] = useState(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await getDiscoveredSegments();
      setData(result);
      return result;
    } catch (err) {
      setError(err.message);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  const convertCluster = useCallback(
    async (clusterId, payload) => {
      setConvertingId(clusterId);
      try {
        const result = await convertClusterToSegment(clusterId, payload);
        return result;
      } finally {
        setConvertingId(null);
      }
    },
    []
  );

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { data, loading, error, refetch, convertCluster, convertingId };
}
