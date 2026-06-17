import { useCallback, useEffect, useState } from "react";
import {
  createSegment as createSegmentRequest,
  deleteSegment as deleteSegmentRequest,
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

  const deleteSegment = useCallback(async (segmentId) => {
    const result = await deleteSegmentRequest(segmentId);
    setData((current) => current.filter((segment) => String(segment.id) !== String(segmentId)));
    return result;
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { data, loading, error, refetch, createSegment, deleteSegment };
}
