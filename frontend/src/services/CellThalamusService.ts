/**
 * Cell Thalamus API Service
 *
 * Service layer for communicating with the Cell Thalamus FastAPI backend
 */

import {
  Design,
  Result,
  MorphologyData,
  DoseResponseData,
  VarianceAnalysis,
  SentinelData,
  RunSimulationRequest,
  SimulationStatus,
  PCAData,
} from '../pages/CellThalamus/types/thalamus';

export class CellThalamusService {
  private baseUrl: string;

  constructor(baseUrl: string = 'http://localhost:8000/api/thalamus') {
    this.baseUrl = baseUrl;
  }

  /**
   * Start a new simulation
   */
  async runSimulation(request: RunSimulationRequest): Promise<Design> {
    const response = await fetch(`${this.baseUrl}/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to start simulation');
    }

    return response.json();
  }

  /**
   * Get all designs (both running and completed)
   */
  async getDesigns(): Promise<Design[]> {
    const response = await fetch(`${this.baseUrl}/designs`);

    if (!response.ok) {
      throw new Error('Failed to fetch designs');
    }

    return response.json();
  }

  /**
   * Check simulation status
   */
  async getSimulationStatus(designId: string): Promise<SimulationStatus> {
    const response = await fetch(`${this.baseUrl}/designs/${designId}/status`);

    if (!response.ok) {
      throw new Error('Failed to fetch simulation status');
    }

    return response.json();
  }

  /**
   * Get all results for a design
   */
  async getResults(designId: string): Promise<Result[]> {
    const response = await fetch(`${this.baseUrl}/designs/${designId}/results`);

    if (!response.ok) {
      throw new Error('Failed to fetch results');
    }

    return response.json();
  }

  /**
   * Get morphology matrix for PCA visualization
   */
  async getMorphologyData(designId: string): Promise<MorphologyData> {
    const response = await fetch(`${this.baseUrl}/designs/${designId}/morphology`);

    if (!response.ok) {
      throw new Error('Failed to fetch morphology data');
    }

    return response.json();
  }

  /**
   * Get real PCA data with optional channel selection
   */
  async getPCAData(designId: string, channels?: string[]): Promise<PCAData> {
    let url = `${this.baseUrl}/designs/${designId}/pca`;

    if (channels && channels.length > 0) {
      const params = new URLSearchParams({
        channels: channels.join(',')
      });
      url += `?${params}`;
    }

    const response = await fetch(url);

    if (!response.ok) {
      throw new Error('Failed to fetch PCA data');
    }

    return response.json();
  }

  /**
   * Get dose-response data for a specific compound/cell line
   */
  async getDoseResponse(
    designId: string,
    compound: string,
    cellLine: string,
    metric: string = 'atp_signal'
  ): Promise<DoseResponseData> {
    const params = new URLSearchParams({
      compound,
      cell_line: cellLine,
      metric,
    });

    const response = await fetch(
      `${this.baseUrl}/designs/${designId}/dose-response?${params}`
    );

    if (!response.ok) {
      throw new Error('Failed to fetch dose-response data');
    }

    return response.json();
  }

  /**
   * Perform variance analysis
   */
  async getVarianceAnalysis(
    designId: string,
    metric: string = 'atp_signal'
  ): Promise<VarianceAnalysis> {
    const params = new URLSearchParams({ metric });
    const response = await fetch(`${this.baseUrl}/designs/${designId}/variance?${params}`);

    if (!response.ok) {
      throw new Error('Failed to fetch variance analysis');
    }

    return response.json();
  }

  /**
   * Get sentinel SPC data
   */
  async getSentinelData(designId: string): Promise<SentinelData[]> {
    const response = await fetch(`${this.baseUrl}/designs/${designId}/sentinels`);

    if (!response.ok) {
      throw new Error('Failed to fetch sentinel data');
    }

    return response.json();
  }

  /**
   * Get data for a specific plate (for heatmap)
   */
  async getPlateData(designId: string, plateId: string): Promise<Result[]> {
    const response = await fetch(
      `${this.baseUrl}/designs/${designId}/plates/${plateId}`
    );

    if (!response.ok) {
      throw new Error('Failed to fetch plate data');
    }

    return response.json();
  }

  /**
   * Poll simulation status until completion or failure
   * @param designId - Design ID to poll
   * @param interval - Polling interval in milliseconds (default: 2000)
   * @param timeout - Maximum time to poll in milliseconds (default: 300000 = 5 minutes)
   */
  async pollSimulationStatus(
    designId: string,
    interval: number = 2000,
    timeout: number = 300000
  ): Promise<SimulationStatus> {
    const startTime = Date.now();

    return new Promise((resolve, reject) => {
      const poll = async () => {
        try {
          const status = await this.getSimulationStatus(designId);

          if (status.status === 'completed' || status.status === 'failed') {
            resolve(status);
            return;
          }

          if (Date.now() - startTime > timeout) {
            reject(new Error('Polling timeout exceeded'));
            return;
          }

          setTimeout(poll, interval);
        } catch (error) {
          reject(error);
        }
      };

      poll();
    });
  }
}

// Export singleton instance
export const cellThalamusService = new CellThalamusService();
