const API_BASE = '/api';

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
  demand?: number;
  time_window_start?: string;
  time_window_end?: string;
  service_time?: number;
  priority?: number;
}

export interface Vehicle {
  id: string;
  name?: string;
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
  arrival_time?: string;
  departure_time?: string;
  cumulative_distance: number;
  cumulative_load: number;
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

export interface OptimizationResult {
  success: boolean;
  message: string;
  routes: Route[];
  unassigned_deliveries: string[];
  total_distance: number;
  total_time: number;
  computation_time: number;
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
  const response = await fetch(`${API_BASE}/optimize`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Optimization failed');
  }

  return response.json();
}

export async function getSampleData(): Promise<SampleData> {
  const response = await fetch(`${API_BASE}/sample-data`);
  if (!response.ok) {
    throw new Error('Failed to fetch sample data');
  }
  return response.json();
}
