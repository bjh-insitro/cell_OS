/**
 * API configuration - single source of truth for API endpoints
 */

export const API_BASE = import.meta.env.VITE_THALAMUS_API_BASE ?? 'http://localhost:8000';

export const API_ENDPOINTS = {
  catalog: `${API_BASE}/api/thalamus/catalog`,
  catalogDesign: (designId: string) => `${API_BASE}/api/thalamus/catalog/designs/${designId}`,
  generateDesign: `${API_BASE}/api/thalamus/generate-design`,
} as const;
