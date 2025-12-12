/**
 * React hook for running Cell Thalamus simulations
 */

import { useState } from 'react';
import { cellThalamusService } from '../../../services/CellThalamusService';
import type { Design, RunSimulationRequest, SimulationStatus } from '../types/thalamus';

interface UseSimulationResult {
  runSimulation: (request: RunSimulationRequest) => Promise<void>;
  design: Design | null;
  status: SimulationStatus | null;
  loading: boolean;
  error: string | null;
  isPolling: boolean;
}

/**
 * Hook for running simulations and polling their status
 */
export function useSimulation(): UseSimulationResult {
  const [design, setDesign] = useState<Design | null>(null);
  const [status, setStatus] = useState<SimulationStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  const runSimulation = async (request: RunSimulationRequest) => {
    try {
      setLoading(true);
      setError(null);
      setDesign(null);
      setStatus(null);

      // Start the simulation
      const newDesign = await cellThalamusService.runSimulation(request);
      setDesign(newDesign);

      // Start polling for completion
      setIsPolling(true);
      const finalStatus = await cellThalamusService.pollSimulationStatus(
        newDesign.design_id,
        2000, // Poll every 2 seconds
        300000 // Timeout after 5 minutes
      );

      setStatus(finalStatus);
      setIsPolling(false);

      if (finalStatus.status === 'failed') {
        setError(finalStatus.error || 'Simulation failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setIsPolling(false);
    } finally {
      setLoading(false);
    }
  };

  return {
    runSimulation,
    design,
    status,
    loading,
    error,
    isPolling,
  };
}
