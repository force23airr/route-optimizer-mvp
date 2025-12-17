"""
cuOpt Service for Route Optimization

This module provides route optimization using NVIDIA cuOpt Cloud API.
Falls back to mock optimization if no API key is configured.
"""

import math
import time
import random
import os
import httpx
from typing import Optional
from models import (
    OptimizationRequest,
    OptimizationResult,
    Route,
    RouteStop,
    LocationBase,
    OptimizationObjective,
    CostSummary,
    SavingsSummary,
    ScenarioMetrics,
    ComparisonSummary,
    GoogleComparisonStatus,
    Depot,
    Delivery,
    Vehicle,
    CostSettings,
)


# NVIDIA cuOpt API constants
CUOPT_API_URL = "https://optimize.api.nvidia.com/v1/nvidia/cuopt"
CUOPT_STATUS_URL = "https://optimize.api.nvidia.com/v1/status/"
CUOPT_MAX_POLL_ATTEMPTS = 60  # Max polling attempts (60 seconds)
CUOPT_POLL_INTERVAL = 1.0  # Seconds between polls

# Google Maps API constants
GOOGLE_MAPS_DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
GOOGLE_MAX_WAYPOINTS = 23  # 25 total - origin - destination


def get_google_maps_route(
    depot: Depot,
    deliveries: list[Delivery],
    api_key: str
) -> tuple[Optional[float], Optional[int], GoogleComparisonStatus, Optional[str]]:
    """
    Call Google Maps Directions API to get optimized route for single vehicle.

    Args:
        depot: Starting/ending location
        deliveries: List of delivery locations
        api_key: Google Maps API key

    Returns:
        Tuple of (distance_km, time_minutes, status, message)
    """
    # Debug: Check if API key is loaded
    if not api_key or not api_key.strip():
        print("[Google API] ERROR: No API key found in environment")
        return None, None, GoogleComparisonStatus.NO_KEY, "Google Maps API key not configured"

    # Debug: Show masked API key
    masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
    print(f"[Google API] Using API key: {masked_key}")

    if not deliveries:
        return 0.0, 0, GoogleComparisonStatus.ACTUAL, None

    # Check waypoint limit
    stops_to_use = deliveries
    status = GoogleComparisonStatus.ACTUAL
    message = None

    if len(deliveries) > GOOGLE_MAX_WAYPOINTS:
        stops_to_use = deliveries[:GOOGLE_MAX_WAYPOINTS]
        status = GoogleComparisonStatus.LIMITED
        message = f"Google limited to {GOOGLE_MAX_WAYPOINTS} stops (you have {len(deliveries)})"

    print(f"[Google API] Requesting route for {len(stops_to_use)} stops")

    # Build waypoints string: optimize:true|lat1,lng1|lat2,lng2|...
    waypoints_list = [f"{d.latitude},{d.longitude}" for d in stops_to_use]
    waypoints = "optimize:true|" + "|".join(waypoints_list)

    # API parameters
    params = {
        "origin": f"{depot.latitude},{depot.longitude}",
        "destination": f"{depot.latitude},{depot.longitude}",
        "waypoints": waypoints,
        "key": api_key,
    }

    # Debug: Log request details (without full key)
    print(f"[Google API] Origin: {params['origin']}")
    print(f"[Google API] Destination: {params['destination']}")
    print(f"[Google API] Waypoints count: {len(waypoints_list)}")

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(GOOGLE_MAPS_DIRECTIONS_URL, params=params)
            data = response.json()

            # Debug: Log full response status
            print(f"[Google API] HTTP Status: {response.status_code}")
            print(f"[Google API] Response status: {data.get('status')}")

            if data.get("status") != "OK":
                error_msg = data.get("error_message", data.get("status", "Unknown error"))
                print(f"[Google API] ERROR: {error_msg}")
                print(f"[Google API] Full response: {data}")
                return None, None, GoogleComparisonStatus.ESTIMATED, f"Google API error: {error_msg}"

        # Extract total distance and duration from all legs
        routes = data.get("routes", [])
        if not routes:
            print("[Google API] ERROR: No routes in response")
            return None, None, GoogleComparisonStatus.ESTIMATED, "No routes returned from Google"

        route = routes[0]
        legs = route.get("legs", [])

        total_distance_m = sum(leg.get("distance", {}).get("value", 0) for leg in legs)
        total_duration_s = sum(leg.get("duration", {}).get("value", 0) for leg in legs)

        # Convert to km and minutes
        distance_km = total_distance_m / 1000.0
        time_minutes = int(total_duration_s / 60)

        # Add service time for each delivery
        service_time = sum(d.service_time for d in stops_to_use)
        time_minutes += service_time

        print(f"[Google API] SUCCESS: {distance_km:.1f} km, {time_minutes} min")
        return distance_km, time_minutes, status, message

    except httpx.HTTPError as e:
        print(f"[Google API] HTTP ERROR: {str(e)}")
        return None, None, GoogleComparisonStatus.ESTIMATED, f"Google API request failed: {str(e)}"
    except Exception as e:
        print(f"[Google API] EXCEPTION: {str(e)}")
        return None, None, GoogleComparisonStatus.ESTIMATED, f"Google API error: {str(e)}"


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
        Call the real NVIDIA cuOpt API for route optimization.
        """
        import traceback

        try:
            return self._call_cuopt_api_inner(request)
        except Exception as e:
            print(f"[cuOpt API] CRITICAL ERROR: {str(e)}")
            print(f"[cuOpt API] Traceback: {traceback.format_exc()}")
            print("[cuOpt API] Falling back to mock optimization due to error")
            return self._mock_optimize(request)

    def _call_cuopt_api_inner(self, request: OptimizationRequest) -> OptimizationResult:
        """
        Inner method for cuOpt API call with full error handling.
        """
        start_time = time.time()

        depot = request.depot
        deliveries = list(request.deliveries)
        vehicles = list(request.vehicles)

        print(f"[cuOpt API] Starting optimization for {len(deliveries)} deliveries with {len(vehicles)} vehicles")

        # Build location list: index 0 = depot, index 1+ = deliveries
        locations = [(depot.latitude, depot.longitude)]
        for d in deliveries:
            locations.append((d.latitude, d.longitude))

        n_locations = len(locations)
        print(f"[cuOpt API] Building {n_locations}x{n_locations} cost/time matrices")

        # Build cost matrix (distances in km) and time matrix (in minutes)
        cost_matrix = []
        time_matrix = []
        for i in range(n_locations):
            cost_row = []
            time_row = []
            for j in range(n_locations):
                if i == j:
                    cost_row.append(0)
                    time_row.append(0)
                else:
                    dist = haversine_distance(
                        locations[i][0], locations[i][1],
                        locations[j][0], locations[j][1]
                    )
                    travel_time = calculate_travel_time(dist)
                    cost_row.append(round(dist, 2))
                    time_row.append(travel_time)
            cost_matrix.append(cost_row)
            time_matrix.append(time_row)

        # Build fleet_data
        vehicle_locations = [[0, 0] for _ in vehicles]  # All start and end at depot (index 0)
        vehicle_ids = [v.id for v in vehicles]
        # Capacities: each inner list is one dimension with values for all vehicles
        # Format: [[v1_cap, v2_cap, ...]] for single dimension
        capacities = [[int(v.capacity) for v in vehicles]]

        # Vehicle time windows (in minutes from midnight)
        vehicle_time_windows = []
        for v in vehicles:
            start = time_to_minutes(v.start_time)
            end = time_to_minutes(v.end_time)
            vehicle_time_windows.append([start, end])

        fleet_data = {
            "vehicle_locations": vehicle_locations,
            "vehicle_ids": vehicle_ids,
            "capacities": capacities,
            "vehicle_time_windows": vehicle_time_windows,
        }

        # Build task_data
        task_locations = list(range(1, len(deliveries) + 1))  # Indices 1, 2, 3, ...
        task_ids = [d.id for d in deliveries]
        # Demand: each inner list is one dimension with values for all tasks
        # Format: [[task1_demand, task2_demand, ...]] for single dimension
        demand = [[int(d.demand) for d in deliveries]]
        service_times = [d.service_time for d in deliveries]

        # Task time windows
        task_time_windows = []
        for d in deliveries:
            if d.time_window_start and d.time_window_end:
                start = time_to_minutes(d.time_window_start)
                end = time_to_minutes(d.time_window_end)
            else:
                # Default: 6 AM to 10 PM
                start = 360
                end = 1320
            task_time_windows.append([start, end])

        task_data = {
            "task_locations": task_locations,
            "task_ids": task_ids,
            "demand": demand,
            "service_times": service_times,
            "task_time_windows": task_time_windows,
        }

        # Solver config based on objective
        objectives = {"cost": 1, "travel_time": 0, "variance_route_size": 0, "variance_route_service_time": 0, "prize": 0}
        if request.objective == OptimizationObjective.MINIMIZE_TIME:
            objectives = {"cost": 0, "travel_time": 1, "variance_route_size": 0, "variance_route_service_time": 0, "prize": 0}
        elif request.objective == OptimizationObjective.BALANCE_ROUTES:
            objectives = {"cost": 0.5, "travel_time": 0.3, "variance_route_size": 0.2, "variance_route_service_time": 0, "prize": 0}

        solver_config = {
            "time_limit": min(request.max_computation_time, 30),
            "objectives": objectives,
            "verbose_mode": False,
            "error_logging": True,
        }

        # Build the full payload
        payload = {
            "action": "cuOpt_OptimizedRouting",
            "data": {
                "cost_waypoint_graph_data": None,
                "travel_time_waypoint_graph_data": None,
                "cost_matrix_data": {
                    "data": {"0": cost_matrix}
                },
                "travel_time_matrix_data": {
                    "data": {"0": time_matrix}
                },
                "fleet_data": fleet_data,
                "task_data": task_data,
                "solver_config": solver_config,
            },
            "client_version": "",
        }

        # NVIDIA NIM API requires Bearer token (nvapi-xxx format from build.nvidia.com)
        masked_key = self.api_key[:12] + "..." if len(self.api_key) > 12 else "***"
        print(f"[cuOpt API] Using Bearer auth with key: {masked_key}")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        print(f"[cuOpt API] Sending request to {CUOPT_API_URL}")

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(CUOPT_API_URL, headers=headers, json=payload)

                print(f"[cuOpt API] Response status: {response.status_code}")

                # Handle async response (202 = processing)
                poll_count = 0
                while response.status_code == 202 and poll_count < CUOPT_MAX_POLL_ATTEMPTS:
                    request_id = response.headers.get("NVCF-REQID")
                    if not request_id:
                        break

                    print(f"[cuOpt API] Polling for results... (attempt {poll_count + 1})")
                    time.sleep(CUOPT_POLL_INTERVAL)

                    fetch_url = CUOPT_STATUS_URL + request_id
                    response = client.get(fetch_url, headers=headers)
                    poll_count += 1

                if response.status_code != 200:
                    error_detail = response.text[:500]
                    print(f"[cuOpt API] Error: {response.status_code} - {error_detail}")
                    # Fall back to mock optimization
                    print("[cuOpt API] Falling back to mock optimization")
                    return self._mock_optimize(request)

                result_data = response.json()
                print(f"[cuOpt API] Got response: {list(result_data.keys()) if isinstance(result_data, dict) else 'non-dict'}")

        except Exception as e:
            print(f"[cuOpt API] Exception: {str(e)}")
            print("[cuOpt API] Falling back to mock optimization")
            return self._mock_optimize(request)

        # Parse cuOpt response
        try:
            routes = self._parse_cuopt_response(result_data, request, locations, deliveries, vehicles)
        except Exception as e:
            print(f"[cuOpt API] Error parsing response: {str(e)}")
            print("[cuOpt API] Falling back to mock optimization")
            return self._mock_optimize(request)

        computation_time = time.time() - start_time

        # Calculate totals
        total_distance = sum(r.total_distance for r in routes)
        total_time = sum(r.total_time for r in routes)

        # Find unassigned deliveries
        assigned_ids = set()
        for route in routes:
            for stop in route.stops:
                assigned_ids.add(stop.delivery_id)
        unassigned = [d.id for d in deliveries if d.id not in assigned_ids]

        # Calculate naive route for comparison
        naive_distance, naive_time = self._calculate_naive_route(depot, deliveries)

        # Calculate savings
        distance_saved = naive_distance - total_distance
        time_saved = naive_time - total_time
        distance_saved_percent = (distance_saved / naive_distance * 100) if naive_distance > 0 else 0
        time_saved_percent = (time_saved / naive_time * 100) if naive_time > 0 else 0

        savings_summary = SavingsSummary(
            naive_distance=round(naive_distance, 2),
            naive_time=naive_time,
            optimized_distance=round(total_distance, 2),
            optimized_time=total_time,
            distance_saved=round(distance_saved, 2),
            time_saved=time_saved,
            distance_saved_percent=round(distance_saved_percent, 1),
            time_saved_percent=round(time_saved_percent, 1),
        )

        # Calculate costs
        cost_summary = None
        if request.cost_settings:
            total_miles = total_distance * 0.621371
            total_hours = total_time / 60
            distance_cost = total_miles * request.cost_settings.cost_per_mile
            time_cost = total_hours * request.cost_settings.cost_per_hour
            total_cost = distance_cost + time_cost

            cost_summary = CostSummary(
                distance_cost=round(distance_cost, 2),
                time_cost=round(time_cost, 2),
                total_cost=round(total_cost, 2),
            )

            naive_miles = naive_distance * 0.621371
            naive_hours = naive_time / 60
            naive_cost = (naive_miles * request.cost_settings.cost_per_mile +
                         naive_hours * request.cost_settings.cost_per_hour)
            savings_summary.money_saved = round(naive_cost - total_cost, 2)

        # Build comparison summary
        comparison_summary = self._build_comparison_summary(
            depot=depot,
            deliveries=deliveries,
            vehicles=vehicles,
            naive_distance=naive_distance,
            naive_time=naive_time,
            optimized_distance=total_distance,
            optimized_time=total_time,
            num_vehicles_used=len(routes),
            cost_settings=request.cost_settings
        )

        print(f"[cuOpt API] Optimization complete: {len(routes)} routes, {total_distance:.1f} km")

        # Debug: Print route details
        for r in routes:
            print(f"[cuOpt API] Route {r.vehicle_id}: {len(r.stops)} stops, {r.total_distance} km, {r.total_time} min, load={r.total_load}, util={r.utilization}%")
            if r.stops:
                print(f"[cuOpt API]   First stop: {r.stops[0].delivery_id}, dist={r.stops[0].cumulative_distance}")

        # Verify all required fields are present
        print(f"[cuOpt API] Result summary: success={True}, routes={len(routes)}, unassigned={len(unassigned)}")

        return OptimizationResult(
            success=True,
            message=f"cuOpt optimization complete. {len(routes)} routes created.",
            routes=routes,
            unassigned_deliveries=unassigned,
            total_distance=round(total_distance, 2),
            total_time=total_time,
            computation_time=round(computation_time, 3),
            cost_summary=cost_summary,
            savings_summary=savings_summary,
            comparison_summary=comparison_summary,
        )

    def _parse_cuopt_response(
        self,
        response_data: dict,
        request: OptimizationRequest,
        locations: list[tuple[float, float]],
        deliveries: list[Delivery],
        vehicles: list[Vehicle]
    ) -> list[Route]:
        """Parse cuOpt API response into Route objects."""

        print(f"[cuOpt API] Parsing response...")
        print(f"[cuOpt API] Full response structure: {list(response_data.keys())}")

        # Navigate to the solver response - handle nested structure
        # Structure: response_data["response"]["solver_response"]["vehicle_data"]
        if "response" in response_data:
            outer_response = response_data["response"]
            print(f"[cuOpt API] Outer response keys: {list(outer_response.keys()) if isinstance(outer_response, dict) else outer_response}")

            if "solver_response" in outer_response:
                solver_response = outer_response["solver_response"]
            else:
                solver_response = outer_response
        else:
            solver_response = response_data

        print(f"[cuOpt API] Solver response keys: {list(solver_response.keys()) if isinstance(solver_response, dict) else 'not a dict'}")

        # Check for dropped tasks
        dropped_tasks = solver_response.get("dropped_tasks", [])
        if dropped_tasks:
            print(f"[cuOpt API] Warning: {len(dropped_tasks)} tasks dropped: {dropped_tasks}")

        # Get vehicle_data which contains the routes
        vehicle_data = solver_response.get("vehicle_data", {})
        print(f"[cuOpt API] Vehicle data keys: {list(vehicle_data.keys()) if isinstance(vehicle_data, dict) else vehicle_data}")

        routes: list[Route] = []
        depot = request.depot

        # vehicle_data contains per-vehicle route info
        # Format: vehicle_data[vehicle_id] = {"task_id": [...], "arrival_stamp": [...], ...}
        for vehicle_idx, vehicle in enumerate(vehicles):
            vehicle_key = str(vehicle_idx)

            if vehicle_key not in vehicle_data:
                # Try vehicle_id directly
                vehicle_key = vehicle.id
                if vehicle_key not in vehicle_data:
                    continue

            vdata = vehicle_data[vehicle_key]
            print(f"[cuOpt API] Vehicle {vehicle_key} data keys: {list(vdata.keys()) if isinstance(vdata, dict) else vdata}")

            # Get task IDs/indices for this vehicle
            task_ids = vdata.get("task_id", vdata.get("route", []))
            arrivals = vdata.get("arrival_stamp", [])

            if not task_ids:
                continue

            # Filter out depot visits (index 0 or "depot")
            task_indices = []
            for tid in task_ids:
                if isinstance(tid, int) and tid > 0:
                    task_indices.append(tid)
                elif isinstance(tid, str) and tid != "depot" and tid.startswith("d"):
                    # Task ID like "d1", "d2" - extract index
                    try:
                        idx = int(tid[1:])
                        task_indices.append(idx)
                    except ValueError:
                        # Try to find by ID in deliveries
                        for i, d in enumerate(deliveries):
                            if d.id == tid:
                                task_indices.append(i + 1)
                                break

            if not task_indices:
                continue

            print(f"[cuOpt API] Vehicle {vehicle_key} has {len(task_indices)} tasks: {task_indices[:5]}...")

            route_stops: list[RouteStop] = []
            current_lat, current_lon = depot.latitude, depot.longitude
            cumulative_distance = 0.0
            cumulative_load = 0.0

            for seq, task_idx in enumerate(task_indices):
                # task_idx is 1-based (0 is depot)
                delivery_idx = task_idx - 1
                if delivery_idx < 0 or delivery_idx >= len(deliveries):
                    continue

                delivery = deliveries[delivery_idx]

                # Calculate distance from previous location
                dist = haversine_distance(
                    current_lat, current_lon,
                    delivery.latitude, delivery.longitude
                )
                cumulative_distance += dist
                cumulative_load += delivery.demand

                # Get arrival time if available
                arrival_time = None
                departure_time = None
                if arrivals and seq < len(arrivals):
                    try:
                        arrival_minutes = int(float(arrivals[seq]))
                        arrival_time = minutes_to_time(arrival_minutes)
                        departure_time = minutes_to_time(arrival_minutes + delivery.service_time)
                    except (ValueError, TypeError):
                        pass

                # Generate directions
                directions = self._get_directions(
                    current_lat, current_lon,
                    delivery.latitude, delivery.longitude,
                    dist
                )

                route_stops.append(RouteStop(
                    sequence=seq + 1,
                    delivery_id=delivery.id,
                    location=LocationBase(
                        latitude=delivery.latitude,
                        longitude=delivery.longitude,
                        address=delivery.address
                    ),
                    customer_name=delivery.name,
                    customer_phone=delivery.phone,
                    arrival_time=arrival_time,
                    departure_time=departure_time,
                    cumulative_distance=round(cumulative_distance, 2),
                    cumulative_load=cumulative_load,
                    directions=directions
                ))

                current_lat, current_lon = delivery.latitude, delivery.longitude

            if route_stops:
                # Add return to depot
                return_dist = haversine_distance(
                    current_lat, current_lon,
                    depot.latitude, depot.longitude
                )
                total_distance = cumulative_distance + return_dist

                # Calculate total time
                total_time_minutes = calculate_travel_time(total_distance)
                total_time_minutes += sum(d.service_time for d in deliveries
                                         if any(s.delivery_id == d.id for s in route_stops))

                routes.append(Route(
                    vehicle_id=vehicle.id,
                    vehicle_name=vehicle.name,
                    stops=route_stops,
                    total_distance=round(total_distance, 2),
                    total_time=total_time_minutes,
                    total_load=cumulative_load,
                    utilization=round((cumulative_load / vehicle.capacity) * 100, 1) if vehicle.capacity > 0 else 0
                ))

        print(f"[cuOpt API] Parsed {len(routes)} routes")
        return routes

    def _get_directions(self, from_lat: float, from_lon: float, to_lat: float, to_lon: float, distance_km: float) -> str:
        """
        Generate simple turn-by-turn directions based on cardinal direction.
        For production, integrate with a routing API like Google Maps, OSRM, or Mapbox.
        """
        lat_diff = to_lat - from_lat
        lon_diff = to_lon - from_lon

        # Determine primary direction
        if abs(lat_diff) > abs(lon_diff):
            primary = "north" if lat_diff > 0 else "south"
        else:
            primary = "east" if lon_diff > 0 else "west"

        # Determine secondary direction if significant
        secondary = ""
        if abs(lat_diff) > 0.001 and abs(lon_diff) > 0.001:
            if abs(lat_diff) > abs(lon_diff):
                secondary = "east" if lon_diff > 0 else "west"
            else:
                secondary = "north" if lat_diff > 0 else "south"

        distance_miles = distance_km * 0.621371

        if secondary:
            return f"Head {primary}, then {secondary} for {distance_miles:.1f} miles"
        else:
            return f"Head {primary} for {distance_miles:.1f} miles"

    def _calculate_naive_route(self, depot, deliveries) -> tuple[float, int]:
        """
        Calculate the naive (unoptimized) route distance and time.
        This visits all deliveries in the order they were provided,
        then returns to depot. Used for savings comparison.
        """
        if not deliveries:
            return 0.0, 0

        total_distance = 0.0
        current_lat = depot.latitude
        current_lon = depot.longitude

        for delivery in deliveries:
            distance = haversine_distance(
                current_lat, current_lon,
                delivery.latitude, delivery.longitude
            )
            total_distance += distance
            current_lat = delivery.latitude
            current_lon = delivery.longitude

        # Return to depot
        total_distance += haversine_distance(
            current_lat, current_lon,
            depot.latitude, depot.longitude
        )

        # Calculate time (assuming 40 km/h average speed)
        total_time = calculate_travel_time(total_distance)

        # Add service time for all deliveries
        total_time += sum(d.service_time for d in deliveries)

        return total_distance, total_time

    def _calculate_single_vehicle_optimized(
        self,
        depot: Depot,
        deliveries: list[Delivery],
        vehicles: list[Vehicle]
    ) -> tuple[float, int]:
        """Calculate optimized route for single vehicle using nearest-neighbor."""
        if not deliveries:
            return 0.0, 0

        # Use first vehicle or create high-capacity vehicle
        vehicle = vehicles[0] if vehicles else Vehicle(
            id="temp_single",
            capacity=99999.0,
            start_time="08:00",
            end_time="23:00"
        )

        # Run nearest-neighbor with single vehicle
        current_lat, current_lon = depot.latitude, depot.longitude
        current_time = time_to_minutes(vehicle.start_time)
        total_distance = 0.0
        remaining = deliveries.copy()

        while remaining:
            # Find nearest delivery
            nearest = min(
                remaining,
                key=lambda d: haversine_distance(current_lat, current_lon, d.latitude, d.longitude)
            )

            distance = haversine_distance(current_lat, current_lon, nearest.latitude, nearest.longitude)
            total_distance += distance
            current_time += calculate_travel_time(distance) + nearest.service_time
            current_lat, current_lon = nearest.latitude, nearest.longitude
            remaining.remove(nearest)

        # Return to depot
        total_distance += haversine_distance(current_lat, current_lon, depot.latitude, depot.longitude)
        total_time = current_time - time_to_minutes(vehicle.start_time)

        return total_distance, total_time

    def _build_comparison_summary(
        self,
        depot: Depot,
        deliveries: list[Delivery],
        vehicles: list[Vehicle],
        naive_distance: float,
        naive_time: int,
        optimized_distance: float,
        optimized_time: int,
        num_vehicles_used: int,
        cost_settings: Optional[CostSettings]
    ) -> ComparisonSummary:
        """Build comparison with all three scenarios, using real Google Maps data when available."""

        # Try to get real Google Maps data
        google_api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
        google_distance, google_time, google_status, google_message = get_google_maps_route(
            depot, deliveries, google_api_key
        )

        # Use Google data if available, otherwise fall back to mock
        if google_distance is not None and google_time is not None:
            single_distance = google_distance
            single_time = google_time
        else:
            # Fall back to mock nearest-neighbor calculation
            single_distance, single_time = self._calculate_single_vehicle_optimized(
                depot, deliveries, vehicles
            )
            if google_status == GoogleComparisonStatus.NO_KEY:
                google_message = "Add GOOGLE_MAPS_API_KEY to .env for real comparison"

        # Build metrics
        unoptimized = ScenarioMetrics(
            total_distance=round(naive_distance, 2),
            total_time=naive_time,
            vehicle_count=1
        )

        single_vehicle = ScenarioMetrics(
            total_distance=round(single_distance, 2),
            total_time=single_time,
            vehicle_count=1
        )

        multi_vehicle = ScenarioMetrics(
            total_distance=round(optimized_distance, 2),
            total_time=optimized_time,
            vehicle_count=num_vehicles_used
        )

        # Add costs if provided
        if cost_settings:
            for scenario in [unoptimized, single_vehicle, multi_vehicle]:
                miles = scenario.total_distance * 0.621371
                hours = scenario.total_time / 60
                scenario.total_cost = round(
                    miles * cost_settings.cost_per_mile + hours * cost_settings.cost_per_hour,
                    2
                )

        return ComparisonSummary(
            unoptimized=unoptimized,
            single_vehicle=single_vehicle,
            multi_vehicle=multi_vehicle,
            google_status=google_status,
            google_message=google_message
        )

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

                # Generate simple directions
                directions = self._get_directions(
                    current_lat, current_lon,
                    best_delivery.latitude, best_delivery.longitude,
                    distance
                )

                route_stops.append(RouteStop(
                    sequence=len(route_stops) + 1,
                    delivery_id=best_delivery.id,
                    location=LocationBase(
                        latitude=best_delivery.latitude,
                        longitude=best_delivery.longitude,
                        address=best_delivery.address
                    ),
                    customer_name=best_delivery.name,
                    customer_phone=best_delivery.phone,
                    arrival_time=minutes_to_time(arrival_time),
                    departure_time=minutes_to_time(departure_time),
                    cumulative_distance=round(cumulative_distance, 2),
                    cumulative_load=current_load,
                    directions=directions
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

        # Calculate naive (unoptimized) route - visit all in order with one vehicle
        naive_distance, naive_time = self._calculate_naive_route(depot, request.deliveries)

        # Calculate savings
        distance_saved = naive_distance - total_distance
        time_saved = naive_time - total_time
        distance_saved_percent = (distance_saved / naive_distance * 100) if naive_distance > 0 else 0
        time_saved_percent = (time_saved / naive_time * 100) if naive_time > 0 else 0

        savings_summary = SavingsSummary(
            naive_distance=round(naive_distance, 2),
            naive_time=naive_time,
            optimized_distance=round(total_distance, 2),
            optimized_time=total_time,
            distance_saved=round(distance_saved, 2),
            time_saved=time_saved,
            distance_saved_percent=round(distance_saved_percent, 1),
            time_saved_percent=round(time_saved_percent, 1),
        )

        # Calculate costs if cost settings provided
        cost_summary = None
        if request.cost_settings:
            # Convert km to miles (1 km = 0.621371 miles)
            total_miles = total_distance * 0.621371
            total_hours = total_time / 60

            distance_cost = total_miles * request.cost_settings.cost_per_mile
            time_cost = total_hours * request.cost_settings.cost_per_hour
            total_cost = distance_cost + time_cost

            cost_summary = CostSummary(
                distance_cost=round(distance_cost, 2),
                time_cost=round(time_cost, 2),
                total_cost=round(total_cost, 2),
            )

            # Calculate money saved
            naive_miles = naive_distance * 0.621371
            naive_hours = naive_time / 60
            naive_cost = (naive_miles * request.cost_settings.cost_per_mile +
                         naive_hours * request.cost_settings.cost_per_hour)
            savings_summary.money_saved = round(naive_cost - total_cost, 2)

        # Build comparison summary
        num_vehicles_used = len(routes)
        comparison_summary = self._build_comparison_summary(
            depot=depot,
            deliveries=request.deliveries,
            vehicles=request.vehicles,
            naive_distance=naive_distance,
            naive_time=naive_time,
            optimized_distance=total_distance,
            optimized_time=total_time,
            num_vehicles_used=num_vehicles_used,
            cost_settings=request.cost_settings
        )

        return OptimizationResult(
            success=True,
            message=f"Optimization complete. {len(routes)} routes created.",
            routes=routes,
            unassigned_deliveries=unassigned,
            total_distance=round(total_distance, 2),
            total_time=total_time,
            computation_time=round(computation_time, 3),
            cost_summary=cost_summary,
            savings_summary=savings_summary,
            comparison_summary=comparison_summary,
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
