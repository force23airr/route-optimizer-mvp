import { useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import Head from 'next/head';
import FileUpload from '@/components/FileUpload';
import RoutesList from '@/components/RoutesList';
import SettingsPanel from '@/components/SettingsPanel';
import {
  uploadDeliveries,
  optimizeRoutes,
  getSampleData,
  type Delivery,
  type Depot,
  type Vehicle,
  type OptimizationResult,
  type CostSettings,
  type CompanySettings,
} from '@/lib/api';

// Dynamic import for MapView to avoid SSR issues with Leaflet
const MapView = dynamic(() => import('@/components/MapView'), {
  ssr: false,
  loading: () => (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
      Loading map...
    </div>
  ),
});

export default function Home() {
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [depot, setDepot] = useState<Depot>({ latitude: 37.7749, longitude: -122.4194 });
  const [vehicles, setVehicles] = useState<Vehicle[]>([
    { id: 'vehicle_1', name: 'Vehicle 1', capacity: 100, start_time: '08:00', end_time: '18:00' },
    { id: 'vehicle_2', name: 'Vehicle 2', capacity: 100, start_time: '08:00', end_time: '18:00' },
  ]);
  const [objective, setObjective] = useState<'minimize_distance' | 'minimize_time' | 'balance_routes'>('minimize_distance');
  const [costSettings, setCostSettings] = useState<CostSettings>({ cost_per_mile: 0.585, cost_per_hour: 25.0 });
  const [companySettings, setCompanySettings] = useState<CompanySettings>({ name: 'My Company' });
  const [result, setResult] = useState<OptimizationResult | null>(null);
  const [selectedRouteIndex, setSelectedRouteIndex] = useState<number | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(false);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = useCallback(async (file: File) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await uploadDeliveries(file);
      setDeliveries(response.deliveries);
      setResult(null);
      setSelectedRouteIndex(undefined);

      // Auto-set depot to centroid of deliveries
      if (response.deliveries.length > 0) {
        const avgLat = response.deliveries.reduce((sum, d) => sum + d.latitude, 0) / response.deliveries.length;
        const avgLon = response.deliveries.reduce((sum, d) => sum + d.longitude, 0) / response.deliveries.length;
        setDepot({ latitude: avgLat, longitude: avgLon });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleOptimize = useCallback(async () => {
    if (deliveries.length === 0) return;

    setIsOptimizing(true);
    setError(null);
    try {
      const response = await optimizeRoutes({
        depot,
        deliveries,
        vehicles,
        objective,
        cost_settings: costSettings,
      });
      setResult(response);
      setSelectedRouteIndex(undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Optimization failed');
    } finally {
      setIsOptimizing(false);
    }
  }, [depot, deliveries, vehicles, objective, costSettings]);

  const handleLoadSample = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getSampleData();
      setDeliveries(data.deliveries);
      setDepot(data.depot);
      setVehicles(data.vehicles);
      setResult(null);
      setSelectedRouteIndex(undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load sample data');
    } finally {
      setIsLoading(false);
    }
  }, []);

  return (
    <>
      <Head>
        <title>Route Optimizer</title>
        <meta name="description" content="Optimize delivery routes" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
        {/* Header */}
        <header
          style={{
            padding: '12px 24px',
            backgroundColor: '#1976d2',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <h1 style={{ margin: 0, fontSize: '20px' }}>Route Optimizer</h1>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            {deliveries.length > 0 && (
              <span style={{ fontSize: '14px' }}>{deliveries.length} deliveries loaded</span>
            )}
            <button
              onClick={handleLoadSample}
              disabled={isLoading}
              style={{
                padding: '6px 12px',
                backgroundColor: 'rgba(255,255,255,0.2)',
                color: '#fff',
                border: '1px solid rgba(255,255,255,0.3)',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '14px',
              }}
            >
              Load Sample Data
            </button>
          </div>
        </header>

        {/* Error Banner */}
        {error && (
          <div
            style={{
              padding: '12px 24px',
              backgroundColor: '#ffebee',
              color: '#c62828',
              borderBottom: '1px solid #ef9a9a',
            }}
          >
            {error}
            <button
              onClick={() => setError(null)}
              style={{
                marginLeft: '12px',
                padding: '2px 8px',
                backgroundColor: 'transparent',
                border: '1px solid #c62828',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Main Content */}
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          {/* Left Panel - Settings */}
          <div
            style={{
              width: '320px',
              borderRight: '1px solid #e0e0e0',
              overflowY: 'auto',
              backgroundColor: '#fff',
            }}
          >
            <div style={{ padding: '16px', borderBottom: '1px solid #e0e0e0' }}>
              <h2 style={{ margin: '0 0 12px 0', fontSize: '16px' }}>Upload Deliveries</h2>
              <FileUpload onFileSelect={handleFileSelect} isLoading={isLoading} />
            </div>
            <SettingsPanel
              depot={depot}
              vehicles={vehicles}
              objective={objective}
              costSettings={costSettings}
              companySettings={companySettings}
              onDepotChange={setDepot}
              onVehiclesChange={setVehicles}
              onObjectiveChange={setObjective}
              onCostSettingsChange={setCostSettings}
              onCompanySettingsChange={setCompanySettings}
              onOptimize={handleOptimize}
              isOptimizing={isOptimizing}
              hasDeliveries={deliveries.length > 0}
            />
          </div>

          {/* Center - Map */}
          <div style={{ flex: 1, position: 'relative' }}>
            <MapView
              depot={depot}
              deliveries={deliveries}
              routes={result?.routes || []}
              selectedRouteIndex={selectedRouteIndex}
            />
          </div>

          {/* Right Panel - Routes */}
          <div
            style={{
              width: '350px',
              borderLeft: '1px solid #e0e0e0',
              overflowY: 'auto',
              backgroundColor: '#fff',
            }}
          >
            <h2 style={{ margin: 0, padding: '16px', borderBottom: '1px solid #e0e0e0', fontSize: '16px' }}>
              Optimized Routes
            </h2>
            <RoutesList
              result={result}
              selectedRouteIndex={selectedRouteIndex}
              onRouteSelect={setSelectedRouteIndex}
              depot={depot}
              costSettings={costSettings}
              companySettings={companySettings}
            />
          </div>
        </div>
      </div>

      <style jsx global>{`
        * {
          box-sizing: border-box;
        }
        html,
        body {
          margin: 0;
          padding: 0;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        }
      `}</style>
    </>
  );
}
