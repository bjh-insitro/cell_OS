/**
 * React hooks for fetching Cell Thalamus data
 */

import { useState, useEffect } from 'react';
import { cellThalamusService } from '../../../services/CellThalamusService';
import type {
  Design,
  Result,
  MorphologyData,
  DoseResponseData,
  VarianceAnalysis,
  SentinelData,
  PCAData,
} from '../types/thalamus';

interface UseDataResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Hook to fetch all designs
 */
export function useDesigns(): UseDataResult<Design[]> {
  const [data, setData] = useState<Design[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refetchTrigger, setRefetchTrigger] = useState(0);

  useEffect(() => {
    let isMounted = true;

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const designs = await cellThalamusService.getDesigns();
        if (isMounted) {
          setData(designs);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Unknown error');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchData();

    return () => {
      isMounted = false;
    };
  }, [refetchTrigger]);

  const refetch = () => setRefetchTrigger((prev) => prev + 1);

  return { data, loading, error, refetch };
}

/**
 * Hook to fetch results for a specific design
 */
export function useResults(designId: string | null): UseDataResult<Result[]> {
  const [data, setData] = useState<Result[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refetchTrigger, setRefetchTrigger] = useState(0);

  useEffect(() => {
    if (!designId) {
      setData(null);
      setLoading(false);
      return;
    }

    let isMounted = true;

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const results = await cellThalamusService.getResults(designId);
        if (isMounted) {
          setData(results);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Unknown error');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchData();

    return () => {
      isMounted = false;
    };
  }, [designId, refetchTrigger]);

  const refetch = () => setRefetchTrigger((prev) => prev + 1);

  return { data, loading, error, refetch };
}

/**
 * Hook to fetch morphology data for PCA visualization
 */
export function useMorphologyData(designId: string | null): UseDataResult<MorphologyData> {
  const [data, setData] = useState<MorphologyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refetchTrigger, setRefetchTrigger] = useState(0);

  useEffect(() => {
    if (!designId) {
      setData(null);
      setLoading(false);
      return;
    }

    let isMounted = true;

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const morphology = await cellThalamusService.getMorphologyData(designId);
        if (isMounted) {
          setData(morphology);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Unknown error');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchData();

    return () => {
      isMounted = false;
    };
  }, [designId, refetchTrigger]);

  const refetch = () => setRefetchTrigger((prev) => prev + 1);

  return { data, loading, error, refetch };
}

/**
 * Hook to fetch dose-response data
 */
export function useDoseResponse(
  designId: string | null,
  compound: string | null,
  cellLine: string | null,
  metric: string = 'atp_signal'
): UseDataResult<DoseResponseData> {
  const [data, setData] = useState<DoseResponseData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refetchTrigger, setRefetchTrigger] = useState(0);

  useEffect(() => {
    if (!designId || !compound || !cellLine) {
      setData(null);
      setLoading(false);
      return;
    }

    let isMounted = true;

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const doseResponse = await cellThalamusService.getDoseResponse(
          designId,
          compound,
          cellLine,
          metric
        );
        if (isMounted) {
          setData(doseResponse);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Unknown error');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchData();

    return () => {
      isMounted = false;
    };
  }, [designId, compound, cellLine, metric, refetchTrigger]);

  const refetch = () => setRefetchTrigger((prev) => prev + 1);

  return { data, loading, error, refetch };
}

/**
 * Hook to fetch variance analysis
 */
export function useVarianceAnalysis(designId: string | null): UseDataResult<VarianceAnalysis> {
  const [data, setData] = useState<VarianceAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refetchTrigger, setRefetchTrigger] = useState(0);

  useEffect(() => {
    if (!designId) {
      setData(null);
      setLoading(false);
      return;
    }

    let isMounted = true;

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const analysis = await cellThalamusService.getVarianceAnalysis(designId);
        if (isMounted) {
          setData(analysis);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Unknown error');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchData();

    return () => {
      isMounted = false;
    };
  }, [designId, refetchTrigger]);

  const refetch = () => setRefetchTrigger((prev) => prev + 1);

  return { data, loading, error, refetch };
}

/**
 * Hook to fetch sentinel data
 */
export function useSentinelData(designId: string | null): UseDataResult<SentinelData[]> {
  const [data, setData] = useState<SentinelData[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refetchTrigger, setRefetchTrigger] = useState(0);

  useEffect(() => {
    if (!designId) {
      setData(null);
      setLoading(false);
      return;
    }

    let isMounted = true;

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const sentinels = await cellThalamusService.getSentinelData(designId);
        if (isMounted) {
          setData(sentinels);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Unknown error');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchData();

    return () => {
      isMounted = false;
    };
  }, [designId, refetchTrigger]);

  const refetch = () => setRefetchTrigger((prev) => prev + 1);

  return { data, loading, error, refetch };
}

/**
 * Hook to fetch plate data
 */
export function usePlateData(
  designId: string | null,
  plateId: string | null
): UseDataResult<Result[]> {
  const [data, setData] = useState<Result[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refetchTrigger, setRefetchTrigger] = useState(0);

  useEffect(() => {
    if (!designId || !plateId) {
      setData(null);
      setLoading(false);
      return;
    }

    let isMounted = true;

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const plate = await cellThalamusService.getPlateData(designId, plateId);
        if (isMounted) {
          setData(plate);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Unknown error');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchData();

    return () => {
      isMounted = false;
    };
  }, [designId, plateId, refetchTrigger]);

  const refetch = () => setRefetchTrigger((prev) => prev + 1);

  return { data, loading, error, refetch };
}

/**
 * Hook to fetch real PCA data with channel selection
 */
export function usePCAData(
  designId: string | null,
  channels: string[] | null = null
): UseDataResult<PCAData> {
  const [data, setData] = useState<PCAData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refetchTrigger, setRefetchTrigger] = useState(0);

  useEffect(() => {
    if (!designId) {
      setData(null);
      setLoading(false);
      return;
    }

    let isMounted = true;

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const pcaData = await cellThalamusService.getPCAData(
          designId,
          channels || undefined
        );
        if (isMounted) {
          setData(pcaData);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Unknown error');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchData();

    return () => {
      isMounted = false;
    };
  }, [designId, refetchTrigger, channels?.join(',')]);

  const refetch = () => setRefetchTrigger((prev) => prev + 1);

  return { data, loading, error, refetch };
}
