const API_BASE = '/api';
// Direct backend URL for long-running requests (bypasses Next.js proxy timeout)
const BACKEND_DIRECT = 'http://localhost:8001/api';

export interface Location {
  latitude: number;
  longitude: number;
  address?: string;
}

export interface Depot extends Location {
  id?: string;
  name?: string;
}

export interface Delivery extends Location {
  id: string;
  name?: string;
  phone?: string;
  notes?: string;
  demand?: number;
  time_window_start?: string;
  time_window_end?: string;
  service_time?: number;
  priority?: number;
}

export interface Vehicle {
  id: string;
  name?: string;
  driver_email?: string;
  capacity?: number;
  max_stops?: number;
  start_time?: string;
  end_time?: string;
  speed_factor?: number;
}

export interface RouteStop {
  sequence: number;
  delivery_id: string;
  location: Location;
  customer_name?: string;
  customer_phone?: string;
  arrival_time?: string;
  departure_time?: string;
  cumulative_distance: number;
  cumulative_load: number;
  directions?: string;
}

export interface Route {
  vehicle_id: string;
  vehicle_name?: string;
  stops: RouteStop[];
  total_distance: number;
  total_time: number;
  total_load: number;
  utilization: number;
}

export interface CostSettings {
  cost_per_mile: number;
  cost_per_hour: number;
}

export interface CompanySettings {
  name: string;
  logo_url?: string;
  address?: string;
  phone?: string;
}

export interface RouteHistoryEntry {
  id: string;
  timestamp: string;
  total_deliveries: number;
  total_routes: number;
  total_distance: number;
  total_time: number;
  total_cost?: number;
}

export interface CostSummary {
  distance_cost: number;
  time_cost: number;
  total_cost: number;
}

export interface SavingsSummary {
  naive_distance: number;
  naive_time: number;
  optimized_distance: number;
  optimized_time: number;
  distance_saved: number;
  time_saved: number;
  distance_saved_percent: number;
  time_saved_percent: number;
  money_saved?: number;
}

export interface ScenarioMetrics {
  total_distance: number;
  total_time: number;
  vehicle_count: number;
  total_cost?: number;
}

export type GoogleComparisonStatus = 'actual' | 'estimated' | 'limited' | 'no_key';

export interface ComparisonSummary {
  unoptimized: ScenarioMetrics;
  single_vehicle: ScenarioMetrics;
  multi_vehicle: ScenarioMetrics;
  google_status: GoogleComparisonStatus;
  google_message?: string;
}

export interface OptimizationResult {
  success: boolean;
  message: string;
  routes: Route[];
  unassigned_deliveries: string[];
  total_distance: number;
  total_time: number;
  computation_time: number;
  cost_summary?: CostSummary;
  savings_summary?: SavingsSummary;
  comparison_summary?: ComparisonSummary;
}

export interface UploadResponse {
  success: boolean;
  message: string;
  deliveries_count: number;
  deliveries: Delivery[];
}

export interface OptimizationRequest {
  depot: Depot;
  deliveries: Delivery[];
  vehicles: Vehicle[];
  objective?: 'minimize_distance' | 'minimize_time' | 'balance_routes';
  max_computation_time?: number;
  cost_settings?: CostSettings;
}

export interface SampleData {
  depot: Depot;
  deliveries: Delivery[];
  vehicles: Vehicle[];
}

export async function checkHealth(): Promise<{ status: string; version: string }> {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) {
    throw new Error('API health check failed');
  }
  return response.json();
}

export async function uploadDeliveries(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Upload failed');
  }

  return response.json();
}

export async function optimizeRoutes(request: OptimizationRequest): Promise<OptimizationResult> {
  console.log('[API] Sending optimize request directly to backend...');
  // Use direct backend URL to bypass Next.js proxy timeout (optimization can take 30+ seconds)
  const response = await fetch(`${BACKEND_DIRECT}/optimize`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  console.log('[API] Response status:', response.status, response.statusText);

  if (!response.ok) {
    const errorText = await response.text();
    console.error('[API] Error response:', errorText);
    try {
      const error = JSON.parse(errorText);
      throw new Error(error.detail || 'Optimization failed');
    } catch {
      throw new Error(errorText || 'Optimization failed');
    }
  }

  const text = await response.text();
  console.log('[API] Response length:', text.length, 'bytes');

  try {
    const result = JSON.parse(text);
    console.log('[API] Parsed result:', result.success, 'routes:', result.routes?.length);
    return result;
  } catch (e) {
    console.error('[API] JSON parse error:', e);
    console.error('[API] Raw response (first 500 chars):', text.substring(0, 500));
    throw new Error('Failed to parse optimization response');
  }
}

export async function getSampleData(): Promise<SampleData> {
  const response = await fetch(`${API_BASE}/sample-data`);
  if (!response.ok) {
    throw new Error('Failed to fetch sample data');
  }
  return response.json();
}

export async function exportRoutePDF(
  routes: Route[],
  depot: Depot,
  costSettings?: CostSettings,
  company?: CompanySettings,
  comparisonSummary?: ComparisonSummary
): Promise<Blob> {
  const response = await fetch(`${API_BASE}/export/pdf`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ routes, depot, cost_settings: costSettings, company, comparison_summary: comparisonSummary }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'PDF export failed');
  }

  return response.blob();
}

export async function saveRouteHistory(
  depot: Depot,
  routes: Route[],
  totalDistance: number,
  totalTime: number,
  totalCost?: number
): Promise<{ success: boolean; id: string; timestamp: string }> {
  const response = await fetch(`${API_BASE}/history/save`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      depot,
      routes,
      total_distance: totalDistance,
      total_time: totalTime,
      total_cost: totalCost,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to save history');
  }

  return response.json();
}

export async function getRouteHistory(): Promise<{ entries: RouteHistoryEntry[] }> {
  const response = await fetch(`${API_BASE}/history`);
  if (!response.ok) {
    throw new Error('Failed to fetch history');
  }
  return response.json();
}

export async function deleteRouteHistory(entryId: string): Promise<{ success: boolean }> {
  const response = await fetch(`${API_BASE}/history/${entryId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error('Failed to delete history entry');
  }
  return response.json();
}

export interface RoadGeometry {
  vehicle_id: string;
  geometry: string | null;
  road_distance?: number;
  road_duration?: number;
  error?: string;
}

export async function getRoadGeometries(
  routes: Route[],
  depot: Depot,
  apiKey?: string
): Promise<{ success: boolean; geometries: RoadGeometry[]; error?: string }> {
  const response = await fetch(`${API_BASE}/road-geometry`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ routes, depot, api_key: apiKey }),
  });

  if (!response.ok) {
    let detail = 'Failed to get road geometries';
    try {
      const error = await response.json();
      detail = error.detail || error.error || detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }

  return response.json();
}
