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
  progress: {
    completed: number;
    total: number;
    percentage: number;
    last_well: string | null;
    completed_wells?: string[];
  } | null;
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
  const [progress, setProgress] = useState<{
    completed: number;
    total: number;
    percentage: number;
    last_well: string | null;
    completed_wells?: string[];
  } | null>(null);

  const runSimulation = async (request: RunSimulationRequest) => {
    try {
      setLoading(true);
      setError(null);
      setDesign(null);
      setStatus(null);
      setProgress(null);

      // Start the simulation
      const newDesign = await cellThalamusService.runSimulation(request);
      setDesign(newDesign);

      // Start polling for completion with progress updates
      setIsPolling(true);

      // Custom polling with progress tracking
      const pollWithProgress = async () => {
        const startTime = Date.now();
        const timeout = 10800000; // 3 hours (safe buffer for Full mode)

        while (true) {
          const currentStatus = await cellThalamusService.getSimulationStatus(newDesign.design_id);

          // Update progress if available
          if (currentStatus.progress) {
            setProgress(currentStatus.progress);
          }

          // Update status
          setStatus(currentStatus);

          if (currentStatus.status === 'completed' || currentStatus.status === 'failed') {
            return currentStatus;
          }

          if (Date.now() - startTime > timeout) {
            throw new Error('Polling timeout exceeded (2 hours)');
          }

          // Poll every 500ms for smooth progress updates
          await new Promise(resolve => setTimeout(resolve, 500));
        }
      };

      const finalStatus = await pollWithProgress();

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
    progress,
  };
}
