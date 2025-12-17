import { useState } from 'react';
import type { Route, OptimizationResult, Depot, CostSettings, CompanySettings } from '@/lib/api';
import { exportRoutePDF, saveRouteHistory } from '@/lib/api';

interface RoutesListProps {
  result: OptimizationResult | null;
  selectedRouteIndex?: number;
  onRouteSelect: (index: number | undefined) => void;
  depot: Depot;
  costSettings: CostSettings;
  companySettings: CompanySettings;
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

export default function RoutesList({ result, selectedRouteIndex, onRouteSelect, depot, costSettings, companySettings }: RoutesListProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  const handleExportPDF = async () => {
    if (!result) return;
    setIsExporting(true);
    try {
      const blob = await exportRoutePDF(result.routes, depot, costSettings, companySettings, result.comparison_summary);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'route_sheets.pdf';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('Failed to export PDF: ' + (err instanceof Error ? err.message : 'Unknown error'));
    } finally {
      setIsExporting(false);
    }
  };

  const handleSaveHistory = async () => {
    if (!result) return;
    setIsSaving(true);
    setSavedMessage(null);
    try {
      const response = await saveRouteHistory(
        depot,
        result.routes,
        result.total_distance,
        result.total_time,
        result.cost_summary?.total_cost
      );
      setSavedMessage(`Saved! ID: ${response.id}`);
      setTimeout(() => setSavedMessage(null), 3000);
    } catch (err) {
      alert('Failed to save: ' + (err instanceof Error ? err.message : 'Unknown error'));
    } finally {
      setIsSaving(false);
    }
  };

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
        {result.cost_summary && (
          <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid #c8e6c9' }}>
            <div style={{ fontSize: '14px', fontWeight: 'bold', color: '#2e7d32' }}>
              Total Cost: ${result.cost_summary.total_cost.toFixed(2)}
            </div>
            <div style={{ fontSize: '12px', color: '#666' }}>
              Distance: ${result.cost_summary.distance_cost.toFixed(2)} | Time: ${result.cost_summary.time_cost.toFixed(2)}
            </div>
          </div>
        )}
        {result.unassigned_deliveries.length > 0 && (
          <p style={{ color: '#c62828', marginTop: '8px', fontSize: '14px' }}>
            Unassigned: {result.unassigned_deliveries.join(', ')}
          </p>
        )}
      </div>

      {/* Savings Summary */}
      {result.savings_summary && result.savings_summary.distance_saved > 0 && (
        <div
          style={{
            backgroundColor: '#e3f2fd',
            padding: '12px',
            borderRadius: '8px',
            marginBottom: '16px',
          }}
        >
          <p style={{ fontWeight: 'bold', marginBottom: '8px', color: '#1565c0' }}>Savings vs. Unoptimized</p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '14px' }}>
            <div>Distance Saved: {result.savings_summary.distance_saved.toFixed(1)} km</div>
            <div>({result.savings_summary.distance_saved_percent.toFixed(1)}%)</div>
            <div>Time Saved: {result.savings_summary.time_saved} min</div>
            <div>({result.savings_summary.time_saved_percent.toFixed(1)}%)</div>
          </div>
          {result.savings_summary.money_saved !== undefined && result.savings_summary.money_saved > 0 && (
            <div style={{ marginTop: '8px', fontSize: '16px', fontWeight: 'bold', color: '#1565c0' }}>
              Money Saved: ${result.savings_summary.money_saved.toFixed(2)}
            </div>
          )}
        </div>
      )}

      {/* Route Comparison Report */}
      {result.comparison_summary && (
        <div style={{
          backgroundColor: '#f5f5f5',
          padding: '16px',
          borderRadius: '8px',
          marginBottom: '16px',
          border: '2px solid #1976d2'
        }}>
          <h3 style={{ margin: '0 0 12px 0', fontSize: '16px', color: '#1976d2' }}>
            📊 Route Comparison Report
          </h3>

          {/* Comparison Table */}
          <div style={{ overflowX: 'auto', marginBottom: '16px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #ddd' }}>
                  <th style={{ textAlign: 'left', padding: '8px', fontWeight: 'bold' }}>Scenario</th>
                  <th style={{ textAlign: 'right', padding: '8px', fontWeight: 'bold' }}>Distance</th>
                  <th style={{ textAlign: 'right', padding: '8px', fontWeight: 'bold' }}>Time</th>
                  <th style={{ textAlign: 'right', padding: '8px', fontWeight: 'bold' }}>Vehicles</th>
                  {result.comparison_summary.multi_vehicle.total_cost !== undefined && (
                    <th style={{ textAlign: 'right', padding: '8px', fontWeight: 'bold' }}>Cost</th>
                  )}
                </tr>
              </thead>
              <tbody>
                <tr style={{ backgroundColor: '#ffebee' }}>
                  <td style={{ padding: '8px' }}>📋 Manual (CSV Order)</td>
                  <td style={{ textAlign: 'right', padding: '8px' }}>
                    {result.comparison_summary.unoptimized.total_distance.toFixed(1)} km
                  </td>
                  <td style={{ textAlign: 'right', padding: '8px' }}>
                    {result.comparison_summary.unoptimized.total_time} min
                  </td>
                  <td style={{ textAlign: 'right', padding: '8px' }}>1 (overworked!)</td>
                  {result.comparison_summary.unoptimized.total_cost !== undefined && (
                    <td style={{ textAlign: 'right', padding: '8px' }}>
                      ${result.comparison_summary.unoptimized.total_cost.toFixed(2)}
                    </td>
                  )}
                </tr>

                <tr style={{ backgroundColor: '#fff3e0' }}>
                  <td style={{ padding: '8px' }}>
                    {result.comparison_summary.google_status === 'actual' ? (
                      <>🗺️ Google Maps (Actual)</>
                    ) : result.comparison_summary.google_status === 'limited' ? (
                      <>🗺️ Google Maps (Partial)*</>
                    ) : (
                      <>🗺️ Single Vehicle (Estimated)</>
                    )}
                  </td>
                  <td style={{ textAlign: 'right', padding: '8px' }}>
                    {result.comparison_summary.single_vehicle.total_distance.toFixed(1)} km
                  </td>
                  <td style={{ textAlign: 'right', padding: '8px' }}>
                    {result.comparison_summary.single_vehicle.total_time} min
                  </td>
                  <td style={{ textAlign: 'right', padding: '8px' }}>Still just 1</td>
                  {result.comparison_summary.single_vehicle.total_cost !== undefined && (
                    <td style={{ textAlign: 'right', padding: '8px' }}>
                      ${result.comparison_summary.single_vehicle.total_cost.toFixed(2)}
                    </td>
                  )}
                </tr>

                <tr style={{ backgroundColor: '#e8f5e9', fontWeight: 'bold' }}>
                  <td style={{ padding: '8px' }}>🚀 Your Optimized Fleet</td>
                  <td style={{ textAlign: 'right', padding: '8px' }}>
                    {result.comparison_summary.multi_vehicle.total_distance.toFixed(1)} km
                  </td>
                  <td style={{ textAlign: 'right', padding: '8px' }}>
                    {result.comparison_summary.multi_vehicle.total_time} min
                  </td>
                  <td style={{ textAlign: 'right', padding: '8px' }}>
                    {result.comparison_summary.multi_vehicle.vehicle_count} (balanced)
                  </td>
                  {result.comparison_summary.multi_vehicle.total_cost !== undefined && (
                    <td style={{ textAlign: 'right', padding: '8px' }}>
                      ${result.comparison_summary.multi_vehicle.total_cost.toFixed(2)}
                    </td>
                  )}
                </tr>
              </tbody>
            </table>
            {result.comparison_summary.google_message && (
              <div style={{
                marginTop: '8px',
                fontSize: '11px',
                color: result.comparison_summary.google_status === 'actual' ? '#2e7d32' :
                       result.comparison_summary.google_status === 'limited' ? '#f57c00' : '#666',
                fontStyle: 'italic'
              }}>
                {result.comparison_summary.google_status === 'actual' && '✓ '}
                {result.comparison_summary.google_status === 'limited' && '* '}
                {result.comparison_summary.google_message}
              </div>
            )}
          </div>

          {/* Savings Section */}
          <div style={{ padding: '12px', backgroundColor: '#e3f2fd', borderRadius: '4px', marginBottom: '12px' }}>
            <div style={{ fontWeight: 'bold', marginBottom: '4px', color: '#1565c0' }}>
              💰 SAVINGS vs Manual:
            </div>
            <div style={{ fontSize: '13px' }}>
              {(result.comparison_summary.unoptimized.total_distance - result.comparison_summary.multi_vehicle.total_distance).toFixed(1)} km saved
              ({(((result.comparison_summary.unoptimized.total_distance - result.comparison_summary.multi_vehicle.total_distance) / result.comparison_summary.unoptimized.total_distance) * 100).toFixed(1)}%)
              {result.comparison_summary.unoptimized.total_cost !== undefined && (
                <> • ${(result.comparison_summary.unoptimized.total_cost - result.comparison_summary.multi_vehicle.total_cost!).toFixed(2)} saved</>
              )}
            </div>
          </div>

          {/* What Google Can't Do */}
          <div style={{ padding: '12px', backgroundColor: '#fff9c4', borderRadius: '4px', borderLeft: '4px solid #fbc02d' }}>
            <div style={{ fontWeight: 'bold', marginBottom: '6px', color: '#f57f17' }}>
              ⚡ WHAT GOOGLE CAN'T DO:
            </div>
            <ul style={{ margin: '6px 0', paddingLeft: '20px', fontSize: '12px', lineHeight: '1.6' }}>
              <li>❌ {result.routes.length} vehicles (max 10 stops per vehicle in Google)</li>
              <li>❌ Capacity limits</li>
              <li>❌ Time windows</li>
              <li>❌ Balanced workload across fleet</li>
            </ul>
            <div style={{ fontSize: '12px', marginTop: '8px', fontStyle: 'italic' }}>
              <strong>Google Maps optimizes for 1 driver. We optimize your entire fleet.</strong>
            </div>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
        <button
          onClick={handleExportPDF}
          disabled={isExporting}
          style={{
            flex: 1,
            padding: '10px',
            backgroundColor: '#ff9800',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: isExporting ? 'not-allowed' : 'pointer',
            fontWeight: 'bold',
            fontSize: '13px',
          }}
        >
          {isExporting ? 'Exporting...' : 'Export PDF'}
        </button>
        <button
          onClick={handleSaveHistory}
          disabled={isSaving}
          style={{
            flex: 1,
            padding: '10px',
            backgroundColor: '#4caf50',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: isSaving ? 'not-allowed' : 'pointer',
            fontWeight: 'bold',
            fontSize: '13px',
          }}
        >
          {isSaving ? 'Saving...' : 'Save History'}
        </button>
      </div>
      {savedMessage && (
        <div style={{ marginBottom: '12px', padding: '8px', backgroundColor: '#e8f5e9', borderRadius: '4px', fontSize: '13px', color: '#2e7d32' }}>
          {savedMessage}
        </div>
      )}

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
                  Stop Details:
                </p>
                <div style={{ fontSize: '12px' }}>
                  {route.stops.map((stop) => (
                    <div key={stop.delivery_id} style={{ marginBottom: '10px', paddingBottom: '8px', borderBottom: '1px solid #f0f0f0' }}>
                      <div style={{ fontWeight: 'bold' }}>
                        {stop.sequence}. {stop.customer_name || stop.delivery_id}
                        {stop.arrival_time && (
                          <span style={{ color: '#666', fontWeight: 'normal' }}> @ {stop.arrival_time}</span>
                        )}
                      </div>
                      {stop.customer_phone && (
                        <div style={{ color: '#1976d2', fontSize: '11px' }}>Phone: {stop.customer_phone}</div>
                      )}
                      {stop.location.address && (
                        <div style={{ color: '#666', fontSize: '11px' }}>{stop.location.address}</div>
                      )}
                      {stop.directions && (
                        <div style={{ color: '#ff9800', fontSize: '11px', fontStyle: 'italic' }}>{stop.directions}</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
