"""
OpenRouteService integration for real road routing.
"""

import os
import httpx
from typing import Optional
import logging

ORS_BASE_URL = "https://api.openrouteservice.org/v2/directions/driving-car"

logger = logging.getLogger(__name__)


async def get_road_route(coordinates: list[list[float]], api_key: Optional[str] = None) -> dict:
    """
    Get road route from OpenRouteService.

    Args:
        coordinates: List of [longitude, latitude] pairs
        api_key: ORS API key (uses env var if not provided)

    Returns:
        GeoJSON geometry of the route
    """
    key = (api_key or os.getenv("ORS_API_KEY", "")).strip()
    if not key:
        raise ValueError("ORS_API_KEY not set. Get a free key at https://openrouteservice.org/dev/#/signup")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            ORS_BASE_URL,
            json={
                "coordinates": coordinates,
                "instructions": False,
                "geometry": True,
            },
            headers={
                "Authorization": key,
                "Content-Type": "application/json",
            },
            timeout=30.0
        )

        if response.status_code != 200:
            error_detail = response.text
            logger.warning("ORS API error %s: %s", response.status_code, error_detail)
            raise Exception(f"ORS API error: {response.status_code} - {error_detail}")

        data = response.json()

        # Extract the route geometry
        if "routes" in data and len(data["routes"]) > 0:
            route = data["routes"][0]
            return {
                "geometry": route.get("geometry"),
                "distance": route.get("summary", {}).get("distance", 0),  # meters
                "duration": route.get("summary", {}).get("duration", 0),  # seconds
            }

        return {"geometry": None, "distance": 0, "duration": 0}


async def get_route_geometries(routes_data: list[dict], depot: dict, api_key: Optional[str] = None) -> list[dict]:
    """
    Get road geometries for multiple optimized routes.

    Args:
        routes_data: List of routes with stops
        depot: Depot location with latitude/longitude
        api_key: ORS API key

    Returns:
        List of route geometries (encoded polylines)
    """
    results = []

    for route in routes_data:
        # Build coordinates: depot -> stops -> depot
        coordinates = [[depot["longitude"], depot["latitude"]]]

        for stop in route.get("stops", []):
            loc = stop.get("location", {})
            coordinates.append([loc.get("longitude"), loc.get("latitude")])

        # Return to depot
        coordinates.append([depot["longitude"], depot["latitude"]])

        try:
            route_data = await get_road_route(coordinates, api_key)
            results.append({
                "vehicle_id": route.get("vehicle_id"),
                "geometry": route_data.get("geometry"),
                "road_distance": route_data.get("distance"),
                "road_duration": route_data.get("duration"),
            })
        except Exception as e:
            # If ORS fails, return None geometry (frontend will fall back to straight lines)
            logger.warning("ORS route failed for vehicle %s: %s", route.get("vehicle_id"), str(e))
            results.append({
                "vehicle_id": route.get("vehicle_id"),
                "geometry": None,
                "error": str(e),
            })

    return results
