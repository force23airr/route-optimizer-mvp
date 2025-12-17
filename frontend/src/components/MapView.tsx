import { useEffect, useRef, useState } from 'react';
import type { Depot, Delivery, Route, RoadGeometry } from '@/lib/api';
import { getRoadGeometries } from '@/lib/api';

interface MapViewProps {
  depot?: Depot;
  deliveries: Delivery[];
  routes: Route[];
  selectedRouteIndex?: number;
  orsApiKey?: string;
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

// Decode Google-style encoded polyline
function decodePolyline(encoded: string): [number, number][] {
  const points: [number, number][] = [];
  let index = 0;
  let lat = 0;
  let lng = 0;

  while (index < encoded.length) {
    let b: number;
    let shift = 0;
    let result = 0;

    do {
      b = encoded.charCodeAt(index++) - 63;
      result |= (b & 0x1f) << shift;
      shift += 5;
    } while (b >= 0x20);

    const dlat = result & 1 ? ~(result >> 1) : result >> 1;
    lat += dlat;

    shift = 0;
    result = 0;

    do {
      b = encoded.charCodeAt(index++) - 63;
      result |= (b & 0x1f) << shift;
      shift += 5;
    } while (b >= 0x20);

    const dlng = result & 1 ? ~(result >> 1) : result >> 1;
    lng += dlng;

    points.push([lat / 1e5, lng / 1e5]);
  }

  return points;
}

export default function MapView({ depot, deliveries, routes, selectedRouteIndex, orsApiKey }: MapViewProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const polylinesLayerRef = useRef<L.LayerGroup | null>(null);
  const [leaflet, setLeaflet] = useState<typeof import('leaflet') | null>(null);
  const [roadGeometries, setRoadGeometries] = useState<RoadGeometry[]>([]);
  const [loadingRoads, setLoadingRoads] = useState(false);
  const [roadError, setRoadError] = useState<string | null>(null);

  // Initialize Leaflet and map once
  useEffect(() => {
    if (typeof window === 'undefined') return;

    let isMounted = true;

    const initLeaflet = async () => {
      const L = await import('leaflet');

      if (!isMounted) return;

      // Fix default marker icon
      delete (L.Icon.Default.prototype as any)._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
        iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
      });

      setLeaflet(L);
    };

    initLeaflet();

    return () => {
      isMounted = false;
    };
  }, []);

  // Create map after Leaflet is loaded
  useEffect(() => {
    if (!leaflet || !mapContainerRef.current || mapRef.current) return;

    const L = leaflet;

    const map = L.map(mapContainerRef.current, {
      center: [37.7749, -122.4194],
      zoom: 12,
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map);

    markersLayerRef.current = L.layerGroup().addTo(map);
    polylinesLayerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
        markersLayerRef.current = null;
        polylinesLayerRef.current = null;
      }
    };
  }, [leaflet]);

  // Fetch road geometries when routes change.
  // If `orsApiKey` is blank, the backend can still use `ORS_API_KEY` from its environment.
  useEffect(() => {
    if (routes.length === 0 || !depot) {
      setRoadGeometries([]);
      setRoadError(null);
      return;
    }

    let cancelled = false;
    setLoadingRoads(true);
    setRoadError(null);

    const trimmedKey = orsApiKey?.trim();

    getRoadGeometries(routes, depot, trimmedKey || undefined)
      .then((response) => {
        if (cancelled) return;
        if (response.success) {
          setRoadGeometries(response.geometries);
          setRoadError(null);
          return;
        }

        setRoadGeometries([]);
        setRoadError(response.error || 'Failed to load road routes');
      })
      .catch((err) => {
        console.error('Failed to get road geometries:', err);
        if (!cancelled) {
          setRoadGeometries([]);
          setRoadError(err instanceof Error ? err.message : String(err));
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingRoads(false);
      });

    return () => {
      cancelled = true;
    };
  }, [routes, depot, orsApiKey]);

  // Update markers and routes when data changes
  useEffect(() => {
    if (!leaflet || !mapRef.current || !markersLayerRef.current || !polylinesLayerRef.current) return;

    const L = leaflet;
    const map = mapRef.current;
    const markersLayer = markersLayerRef.current;
    const polylinesLayer = polylinesLayerRef.current;

    // Clear existing layers
    markersLayer.clearLayers();
    polylinesLayer.clearLayers();

    const bounds: [number, number][] = [];

    // Add depot marker
    if (depot) {
      const depotIcon = L.divIcon({
        html: '<div style="background:#000;color:#fff;padding:4px 8px;border-radius:4px;font-weight:bold;font-size:12px;white-space:nowrap;">DEPOT</div>',
        className: 'depot-marker',
        iconSize: [60, 24],
        iconAnchor: [30, 12],
      });

      L.marker([depot.latitude, depot.longitude], { icon: depotIcon })
        .bindPopup(`<b>Depot</b><br/>${depot.address || 'Starting location'}`)
        .addTo(markersLayer);

      bounds.push([depot.latitude, depot.longitude]);
    }

    // Draw routes or just deliveries
    if (routes.length > 0) {
      routes.forEach((route, routeIndex) => {
        const color = ROUTE_COLORS[routeIndex % ROUTE_COLORS.length];
        const isSelected = selectedRouteIndex === undefined || selectedRouteIndex === routeIndex;
        const opacity = isSelected ? 1 : 0.3;

        // Check if we have road geometry for this route
        const roadGeom = roadGeometries.find((g) => g.vehicle_id === route.vehicle_id);

        if (roadGeom?.geometry) {
          // Use real road path
          const roadPoints = decodePolyline(roadGeom.geometry);
          L.polyline(roadPoints, {
            color,
            weight: 4,
            opacity: opacity * 0.8,
          }).addTo(polylinesLayer);
        } else {
          // Fall back to straight lines
          const points: [number, number][] = [];
          if (depot) {
            points.push([depot.latitude, depot.longitude]);
          }

          route.stops.forEach((stop) => {
            points.push([stop.location.latitude, stop.location.longitude]);
          });

          if (depot) {
            points.push([depot.latitude, depot.longitude]);
          }

          L.polyline(points, {
            color,
            weight: 4,
            opacity: opacity * 0.8,
            dashArray: roadGeometries.length > 0 ? '5, 10' : undefined, // Dashed if others have roads
          }).addTo(polylinesLayer);
        }

        // Add stop markers
        route.stops.forEach((stop, stopIndex) => {
          bounds.push([stop.location.latitude, stop.location.longitude]);

          const numberIcon = L.divIcon({
            html: `<div style="background:${color};color:#fff;width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:12px;border:2px solid #fff;box-shadow:0 2px 4px rgba(0,0,0,0.3);">${stopIndex + 1}</div>`,
            className: 'number-marker',
            iconSize: [24, 24],
            iconAnchor: [12, 12],
          });

          const delivery = deliveries.find((d) => d.id === stop.delivery_id);

          const popupContent = `
            <b>${stop.customer_name || delivery?.name || stop.delivery_id}</b><br/>
            ${stop.location.address ? `${stop.location.address}<br/>` : ''}
            ${stop.customer_phone ? `<span style="color:#1976d2;">Phone: ${stop.customer_phone}</span><br/>` : ''}
            <small>Arrival: ${stop.arrival_time || 'N/A'} | Distance: ${stop.cumulative_distance.toFixed(1)} km</small>
            ${stop.directions ? `<br/><i style="color:#ff9800;font-size:11px;">${stop.directions}</i>` : ''}
          `;

          L.marker([stop.location.latitude, stop.location.longitude], { icon: numberIcon, opacity })
            .bindPopup(popupContent)
            .addTo(markersLayer);
        });
      });
    } else {
      // Just show delivery points
      deliveries.forEach((delivery) => {
        bounds.push([delivery.latitude, delivery.longitude]);

        const deliveryPopup = `
          <b>${delivery.name || delivery.id}</b><br/>
          ${delivery.address ? `${delivery.address}<br/>` : ''}
          ${delivery.phone ? `<span style="color:#1976d2;">Phone: ${delivery.phone}</span><br/>` : ''}
          <small>Demand: ${delivery.demand || 1}</small>
        `;

        L.marker([delivery.latitude, delivery.longitude])
          .bindPopup(deliveryPopup)
          .addTo(markersLayer);
      });
    }

    // Fit bounds if we have points
    if (bounds.length > 0) {
      try {
        map.fitBounds(bounds, { padding: [50, 50], animate: false });
      } catch (e) {
        // Ignore fitBounds errors
      }
    }
  }, [leaflet, depot, deliveries, routes, selectedRouteIndex, roadGeometries]);

  return (
    <>
      <link
        rel="stylesheet"
        href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"
      />
      <div ref={mapContainerRef} style={{ width: '100%', height: '100%', minHeight: '400px' }} />
      {loadingRoads && (
        <div style={{
          position: 'absolute',
          top: '10px',
          left: '50%',
          transform: 'translateX(-50%)',
          background: 'rgba(0,0,0,0.7)',
          color: '#fff',
          padding: '8px 16px',
          borderRadius: '4px',
          fontSize: '12px',
          zIndex: 1000,
        }}>
          Loading road routes...
        </div>
      )}
      {roadError && !loadingRoads && (
        <div style={{
          position: 'absolute',
          top: '10px',
          left: '50%',
          transform: 'translateX(-50%)',
          background: 'rgba(244,67,54,0.92)',
          color: '#fff',
          padding: '8px 12px',
          borderRadius: '4px',
          fontSize: '12px',
          zIndex: 1000,
          maxWidth: 'min(680px, 90vw)',
          textAlign: 'center',
        }}>
          Road routes unavailable: {roadError}
        </div>
      )}
    </>
  );
}
