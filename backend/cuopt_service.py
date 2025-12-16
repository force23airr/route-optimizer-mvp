"""
Mock cuOpt Service for Route Optimization

This module provides a mock implementation of route optimization.
Replace with actual NVIDIA cuOpt API calls when credentials are available.
"""

import math
import time
import random
from typing import Optional
from models import (
    OptimizationRequest,
    OptimizationResult,
    Route,
    RouteStop,
    LocationBase,
    OptimizationObjective,
)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers."""
    R = 6371  # Earth's radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def calculate_travel_time(distance_km: float, speed_factor: float = 1.0) -> int:
    """Calculate travel time in minutes assuming 40 km/h average speed."""
    avg_speed = 40 * speed_factor  # km/h
    return int((distance_km / avg_speed) * 60)


def time_to_minutes(time_str: str) -> int:
    """Convert HH:MM or just hours to minutes from midnight."""
    if not time_str:
        return 480  # Default to 08:00
    try:
        time_str = str(time_str).strip()
        if ":" in time_str:
            parts = time_str.split(":")
            return int(parts[0]) * 60 + int(parts[1])
        else:
            # Just hours (e.g., "9" or "14")
            return int(float(time_str)) * 60
    except (ValueError, IndexError):
        return 480  # Default to 08:00


def minutes_to_time(minutes: int) -> str:
    """Convert minutes from midnight to HH:MM."""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


class MockCuOptService:
    """
    Mock route optimization service.

    Uses a nearest-neighbor heuristic with capacity constraints.
    For production, replace with NVIDIA cuOpt API calls.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.use_real_api = bool(api_key and api_key.strip())

    def optimize(self, request: OptimizationRequest) -> OptimizationResult:
        """
        Run route optimization on the given request.

        Args:
            request: OptimizationRequest with depot, deliveries, and vehicles

        Returns:
            OptimizationResult with optimized routes
        """
        start_time = time.time()

        if self.use_real_api:
            return self._call_cuopt_api(request)
        else:
            return self._mock_optimize(request)

    def _call_cuopt_api(self, request: OptimizationRequest) -> OptimizationResult:
        """
        Call the real NVIDIA cuOpt API.

        TODO: Implement actual cuOpt API integration
        """
        # Placeholder for real API integration
        # See: https://docs.nvidia.com/cuopt/
        raise NotImplementedError("Real cuOpt API not yet implemented")

    def _mock_optimize(self, request: OptimizationRequest) -> OptimizationResult:
        """
        Mock optimization using nearest-neighbor heuristic.
        """
        start_time = time.time()

        depot = request.depot
        deliveries = list(request.deliveries)
        vehicles = list(request.vehicles)

        # Sort deliveries by priority (lower = higher priority)
        deliveries.sort(key=lambda d: d.priority)

        routes: list[Route] = []
        assigned_delivery_ids: set[str] = set()

        for vehicle in vehicles:
            if not deliveries:
                break

            route_stops: list[RouteStop] = []
            current_lat = depot.latitude
            current_lon = depot.longitude
            current_load = 0.0
            cumulative_distance = 0.0
            current_time = time_to_minutes(vehicle.start_time)
            end_time = time_to_minutes(vehicle.end_time)

            remaining_deliveries = [d for d in deliveries if d.id not in assigned_delivery_ids]

            while remaining_deliveries:
                # Find nearest feasible delivery
                best_delivery = None
                best_distance = float('inf')

                for delivery in remaining_deliveries:
                    # Check capacity constraint
                    if current_load + delivery.demand > vehicle.capacity:
                        continue

                    # Check max stops constraint
                    if vehicle.max_stops and len(route_stops) >= vehicle.max_stops:
                        continue

                    # Calculate distance
                    distance = haversine_distance(
                        current_lat, current_lon,
                        delivery.latitude, delivery.longitude
                    )

                    # Check time window if specified
                    travel_time = calculate_travel_time(distance, vehicle.speed_factor)
                    arrival = current_time + travel_time

                    if delivery.time_window_end:
                        window_end = time_to_minutes(delivery.time_window_end)
                        if arrival > window_end:
                            continue

                    # Check if we can return to depot in time
                    return_distance = haversine_distance(
                        delivery.latitude, delivery.longitude,
                        depot.latitude, depot.longitude
                    )
                    return_time = calculate_travel_time(return_distance, vehicle.speed_factor)

                    if arrival + delivery.service_time + return_time > end_time:
                        continue

                    # Scoring based on objective
                    if request.objective == OptimizationObjective.MINIMIZE_DISTANCE:
                        score = distance
                    elif request.objective == OptimizationObjective.MINIMIZE_TIME:
                        score = travel_time
                    else:  # BALANCE_ROUTES
                        score = distance * (1 + len(route_stops) * 0.1)

                    if score < best_distance:
                        best_distance = score
                        best_delivery = delivery

                if best_delivery is None:
                    break

                # Add delivery to route
                distance = haversine_distance(
                    current_lat, current_lon,
                    best_delivery.latitude, best_delivery.longitude
                )
                travel_time = calculate_travel_time(distance, vehicle.speed_factor)

                cumulative_distance += distance
                current_load += best_delivery.demand
                arrival_time = current_time + travel_time

                # Wait for time window if needed
                if best_delivery.time_window_start:
                    window_start = time_to_minutes(best_delivery.time_window_start)
                    if arrival_time < window_start:
                        arrival_time = window_start

                departure_time = arrival_time + best_delivery.service_time

                route_stops.append(RouteStop(
                    sequence=len(route_stops) + 1,
                    delivery_id=best_delivery.id,
                    location=LocationBase(
                        latitude=best_delivery.latitude,
                        longitude=best_delivery.longitude,
                        address=best_delivery.address
                    ),
                    arrival_time=minutes_to_time(arrival_time),
                    departure_time=minutes_to_time(departure_time),
                    cumulative_distance=round(cumulative_distance, 2),
                    cumulative_load=current_load
                ))

                assigned_delivery_ids.add(best_delivery.id)
                remaining_deliveries = [d for d in remaining_deliveries if d.id != best_delivery.id]

                current_lat = best_delivery.latitude
                current_lon = best_delivery.longitude
                current_time = departure_time

            if route_stops:
                # Add return to depot distance
                return_distance = haversine_distance(
                    current_lat, current_lon,
                    depot.latitude, depot.longitude
                )
                cumulative_distance += return_distance
                return_time = calculate_travel_time(return_distance, vehicle.speed_factor)

                total_time = current_time + return_time - time_to_minutes(vehicle.start_time)

                routes.append(Route(
                    vehicle_id=vehicle.id,
                    vehicle_name=vehicle.name,
                    stops=route_stops,
                    total_distance=round(cumulative_distance, 2),
                    total_time=total_time,
                    total_load=current_load,
                    utilization=round((current_load / vehicle.capacity) * 100, 1)
                ))

        # Find unassigned deliveries
        unassigned = [d.id for d in request.deliveries if d.id not in assigned_delivery_ids]

        computation_time = time.time() - start_time

        total_distance = sum(r.total_distance for r in routes)
        total_time = sum(r.total_time for r in routes)

        return OptimizationResult(
            success=True,
            message=f"Optimization complete. {len(routes)} routes created.",
            routes=routes,
            unassigned_deliveries=unassigned,
            total_distance=round(total_distance, 2),
            total_time=total_time,
            computation_time=round(computation_time, 3)
        )


# Singleton instance
_service: Optional[MockCuOptService] = None


def get_cuopt_service() -> MockCuOptService:
    """Get or create the cuOpt service instance."""
    global _service
    if _service is None:
        import os
        api_key = os.getenv("CUOPT_API_KEY")
        _service = MockCuOptService(api_key=api_key)
    return _service
