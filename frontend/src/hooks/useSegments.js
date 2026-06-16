import { useCallback, useEffect, useState } from "react";
import {
  createSegment as createSegmentRequest,
  getSegments
} from "@/services/segmentsApi";

export function useSegments() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await getSegments();
      setData(result);
      return result;
    } catch (err) {
      setError(err.message);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  const createSegment = useCallback(
    async (payload) => {
      const result = await createSegmentRequest(payload);
      await refetch();
      return result;
    },
    [refetch]
  );

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { data, loading, error, refetch, createSegment };
}
