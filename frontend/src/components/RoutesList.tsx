import type { Route, OptimizationResult } from '@/lib/api';

interface RoutesListProps {
  result: OptimizationResult | null;
  selectedRouteIndex?: number;
  onRouteSelect: (index: number | undefined) => void;
}

const ROUTE_COLORS = [
  '#e41a1c',
  '#377eb8',
  '#4daf4a',
  '#984ea3',
  '#ff7f00',
  '#ffff33',
  '#a65628',
  '#f781bf',
];

export default function RoutesList({ result, selectedRouteIndex, onRouteSelect }: RoutesListProps) {
  if (!result) {
    return (
      <div style={{ padding: '20px', color: '#666', textAlign: 'center' }}>
        <p>No optimization results yet.</p>
        <p style={{ fontSize: '14px' }}>Upload deliveries and run optimization to see routes.</p>
      </div>
    );
  }

  return (
    <div style={{ padding: '16px' }}>
      {/* Summary */}
      <div
        style={{
          backgroundColor: result.success ? '#e8f5e9' : '#ffebee',
          padding: '12px',
          borderRadius: '8px',
          marginBottom: '16px',
        }}
      >
        <p style={{ fontWeight: 'bold', marginBottom: '8px' }}>{result.message}</p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '14px' }}>
          <div>Total Distance: {result.total_distance.toFixed(1)} km</div>
          <div>Total Time: {result.total_time} min</div>
          <div>Routes: {result.routes.length}</div>
          <div>Compute: {result.computation_time.toFixed(3)}s</div>
        </div>
        {result.unassigned_deliveries.length > 0 && (
          <p style={{ color: '#c62828', marginTop: '8px', fontSize: '14px' }}>
            Unassigned: {result.unassigned_deliveries.join(', ')}
          </p>
        )}
      </div>

      {/* Show all button */}
      <button
        onClick={() => onRouteSelect(undefined)}
        style={{
          width: '100%',
          padding: '8px',
          marginBottom: '12px',
          backgroundColor: selectedRouteIndex === undefined ? '#1976d2' : '#f5f5f5',
          color: selectedRouteIndex === undefined ? '#fff' : '#333',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
        }}
      >
        Show All Routes
      </button>

      {/* Routes */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {result.routes.map((route, index) => (
          <div
            key={route.vehicle_id}
            onClick={() => onRouteSelect(index)}
            style={{
              border: `2px solid ${ROUTE_COLORS[index % ROUTE_COLORS.length]}`,
              borderRadius: '8px',
              padding: '12px',
              cursor: 'pointer',
              backgroundColor: selectedRouteIndex === index ? '#f0f7ff' : '#fff',
              transition: 'all 0.2s ease',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '8px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div
                  style={{
                    width: '16px',
                    height: '16px',
                    borderRadius: '50%',
                    backgroundColor: ROUTE_COLORS[index % ROUTE_COLORS.length],
                  }}
                />
                <span style={{ fontWeight: 'bold' }}>
                  {route.vehicle_name || route.vehicle_id}
                </span>
              </div>
              <span
                style={{
                  fontSize: '12px',
                  backgroundColor: '#e3f2fd',
                  padding: '2px 8px',
                  borderRadius: '4px',
                }}
              >
                {route.stops.length} stops
              </span>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '4px',
                fontSize: '13px',
                color: '#666',
              }}
            >
              <div>Distance: {route.total_distance.toFixed(1)} km</div>
              <div>Time: {route.total_time} min</div>
              <div>Load: {route.total_load}</div>
              <div>Utilization: {route.utilization}%</div>
            </div>

            {selectedRouteIndex === index && (
              <div style={{ marginTop: '12px', borderTop: '1px solid #eee', paddingTop: '12px' }}>
                <p style={{ fontSize: '12px', fontWeight: 'bold', marginBottom: '8px' }}>
                  Stop Sequence:
                </p>
                <ol style={{ margin: 0, paddingLeft: '20px', fontSize: '12px' }}>
                  {route.stops.map((stop) => (
                    <li key={stop.delivery_id} style={{ marginBottom: '4px' }}>
                      {stop.delivery_id}
                      {stop.arrival_time && (
                        <span style={{ color: '#666' }}> @ {stop.arrival_time}</span>
                      )}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
