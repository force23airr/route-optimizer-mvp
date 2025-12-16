import { useEffect, useRef, useState } from 'react';
import type { Depot, Delivery, Route } from '@/lib/api';

interface MapViewProps {
  depot?: Depot;
  deliveries: Delivery[];
  routes: Route[];
  selectedRouteIndex?: number;
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

export default function MapView({ depot, deliveries, routes, selectedRouteIndex }: MapViewProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const polylinesLayerRef = useRef<L.LayerGroup | null>(null);
  const [leaflet, setLeaflet] = useState<typeof import('leaflet') | null>(null);

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

        // Create route polyline
        const points: [number, number][] = [];
        if (depot) {
          points.push([depot.latitude, depot.longitude]);
        }

        route.stops.forEach((stop, stopIndex) => {
          points.push([stop.location.latitude, stop.location.longitude]);
          bounds.push([stop.location.latitude, stop.location.longitude]);

          // Add numbered marker
          const numberIcon = L.divIcon({
            html: `<div style="background:${color};color:#fff;width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:12px;border:2px solid #fff;box-shadow:0 2px 4px rgba(0,0,0,0.3);">${stopIndex + 1}</div>`,
            className: 'number-marker',
            iconSize: [24, 24],
            iconAnchor: [12, 12],
          });

          const delivery = deliveries.find((d) => d.id === stop.delivery_id);

          L.marker([stop.location.latitude, stop.location.longitude], { icon: numberIcon, opacity })
            .bindPopup(
              `<b>${delivery?.name || stop.delivery_id}</b><br/>
               ${stop.location.address || ''}<br/>
               <small>Arrival: ${stop.arrival_time || 'N/A'}<br/>
               Distance: ${stop.cumulative_distance.toFixed(1)} km</small>`
            )
            .addTo(markersLayer);
        });

        // Return to depot
        if (depot) {
          points.push([depot.latitude, depot.longitude]);
        }

        L.polyline(points, {
          color,
          weight: 4,
          opacity: opacity * 0.8,
        }).addTo(polylinesLayer);
      });
    } else {
      // Just show delivery points
      deliveries.forEach((delivery) => {
        bounds.push([delivery.latitude, delivery.longitude]);

        L.marker([delivery.latitude, delivery.longitude])
          .bindPopup(
            `<b>${delivery.name || delivery.id}</b><br/>
             ${delivery.address || ''}<br/>
             <small>Demand: ${delivery.demand || 1}</small>`
          )
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
  }, [leaflet, depot, deliveries, routes, selectedRouteIndex]);

  return (
    <>
      <link
        rel="stylesheet"
        href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"
      />
      <div ref={mapContainerRef} style={{ width: '100%', height: '100%', minHeight: '400px' }} />
    </>
  );
}
