import type { Depot, Vehicle } from '@/lib/api';

interface SettingsPanelProps {
  depot: Depot;
  vehicles: Vehicle[];
  objective: 'minimize_distance' | 'minimize_time' | 'balance_routes';
  onDepotChange: (depot: Depot) => void;
  onVehiclesChange: (vehicles: Vehicle[]) => void;
  onObjectiveChange: (objective: 'minimize_distance' | 'minimize_time' | 'balance_routes') => void;
  onOptimize: () => void;
  isOptimizing: boolean;
  hasDeliveries: boolean;
}

export default function SettingsPanel({
  depot,
  vehicles,
  objective,
  onDepotChange,
  onVehiclesChange,
  onObjectiveChange,
  onOptimize,
  isOptimizing,
  hasDeliveries,
}: SettingsPanelProps) {
  const addVehicle = () => {
    const newVehicle: Vehicle = {
      id: `vehicle_${vehicles.length + 1}`,
      name: `Vehicle ${vehicles.length + 1}`,
      capacity: 100,
      start_time: '08:00',
      end_time: '18:00',
    };
    onVehiclesChange([...vehicles, newVehicle]);
  };

  const removeVehicle = (index: number) => {
    if (vehicles.length > 1) {
      onVehiclesChange(vehicles.filter((_, i) => i !== index));
    }
  };

  const updateVehicle = (index: number, updates: Partial<Vehicle>) => {
    const updated = [...vehicles];
    updated[index] = { ...updated[index], ...updates };
    onVehiclesChange(updated);
  };

  return (
    <div style={{ padding: '16px' }}>
      {/* Depot Settings */}
      <section style={{ marginBottom: '24px' }}>
        <h3 style={{ marginBottom: '12px', fontSize: '16px' }}>Depot Location</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', color: '#666', marginBottom: '4px' }}>
              Latitude
            </label>
            <input
              type="number"
              step="0.0001"
              value={depot.latitude}
              onChange={(e) => onDepotChange({ ...depot, latitude: parseFloat(e.target.value) || 0 })}
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #ddd',
                borderRadius: '4px',
              }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '12px', color: '#666', marginBottom: '4px' }}>
              Longitude
            </label>
            <input
              type="number"
              step="0.0001"
              value={depot.longitude}
              onChange={(e) => onDepotChange({ ...depot, longitude: parseFloat(e.target.value) || 0 })}
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #ddd',
                borderRadius: '4px',
              }}
            />
          </div>
        </div>
      </section>

      {/* Optimization Objective */}
      <section style={{ marginBottom: '24px' }}>
        <h3 style={{ marginBottom: '12px', fontSize: '16px' }}>Optimization Objective</h3>
        <select
          value={objective}
          onChange={(e) => onObjectiveChange(e.target.value as any)}
          style={{
            width: '100%',
            padding: '8px',
            border: '1px solid #ddd',
            borderRadius: '4px',
          }}
        >
          <option value="minimize_distance">Minimize Total Distance</option>
          <option value="minimize_time">Minimize Total Time</option>
          <option value="balance_routes">Balance Routes Evenly</option>
        </select>
      </section>

      {/* Vehicles */}
      <section style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <h3 style={{ fontSize: '16px', margin: 0 }}>Vehicles ({vehicles.length})</h3>
          <button
            onClick={addVehicle}
            style={{
              padding: '4px 12px',
              backgroundColor: '#4caf50',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '14px',
            }}
          >
            + Add
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '300px', overflowY: 'auto' }}>
          {vehicles.map((vehicle, index) => (
            <div
              key={vehicle.id}
              style={{
                border: '1px solid #ddd',
                borderRadius: '8px',
                padding: '12px',
                backgroundColor: '#fafafa',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <input
                  type="text"
                  value={vehicle.name || ''}
                  onChange={(e) => updateVehicle(index, { name: e.target.value })}
                  placeholder="Vehicle name"
                  style={{
                    padding: '4px 8px',
                    border: '1px solid #ddd',
                    borderRadius: '4px',
                    fontWeight: 'bold',
                  }}
                />
                {vehicles.length > 1 && (
                  <button
                    onClick={() => removeVehicle(index)}
                    style={{
                      padding: '4px 8px',
                      backgroundColor: '#f44336',
                      color: '#fff',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '12px',
                    }}
                  >
                    Remove
                  </button>
                )}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#666' }}>Capacity</label>
                  <input
                    type="number"
                    value={vehicle.capacity || 100}
                    onChange={(e) => updateVehicle(index, { capacity: parseFloat(e.target.value) || 100 })}
                    style={{
                      width: '100%',
                      padding: '4px',
                      border: '1px solid #ddd',
                      borderRadius: '4px',
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#666' }}>Max Stops</label>
                  <input
                    type="number"
                    value={vehicle.max_stops || ''}
                    placeholder="No limit"
                    onChange={(e) =>
                      updateVehicle(index, {
                        max_stops: e.target.value ? parseInt(e.target.value) : undefined,
                      })
                    }
                    style={{
                      width: '100%',
                      padding: '4px',
                      border: '1px solid #ddd',
                      borderRadius: '4px',
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#666' }}>Start Time</label>
                  <input
                    type="time"
                    value={vehicle.start_time || '08:00'}
                    onChange={(e) => updateVehicle(index, { start_time: e.target.value })}
                    style={{
                      width: '100%',
                      padding: '4px',
                      border: '1px solid #ddd',
                      borderRadius: '4px',
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#666' }}>End Time</label>
                  <input
                    type="time"
                    value={vehicle.end_time || '18:00'}
                    onChange={(e) => updateVehicle(index, { end_time: e.target.value })}
                    style={{
                      width: '100%',
                      padding: '4px',
                      border: '1px solid #ddd',
                      borderRadius: '4px',
                    }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Optimize Button */}
      <button
        onClick={onOptimize}
        disabled={isOptimizing || !hasDeliveries}
        style={{
          width: '100%',
          padding: '16px',
          backgroundColor: hasDeliveries ? '#1976d2' : '#ccc',
          color: '#fff',
          border: 'none',
          borderRadius: '8px',
          cursor: hasDeliveries && !isOptimizing ? 'pointer' : 'not-allowed',
          fontSize: '16px',
          fontWeight: 'bold',
        }}
      >
        {isOptimizing ? 'Optimizing...' : hasDeliveries ? 'Optimize Routes' : 'Upload Deliveries First'}
      </button>
    </div>
  );
}
