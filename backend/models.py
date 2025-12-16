from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class LocationBase(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: Optional[str] = None


class Depot(LocationBase):
    id: str = "depot"
    name: str = "Depot"


class Delivery(LocationBase):
    id: str
    name: Optional[str] = None
    demand: float = Field(default=1.0, ge=0, description="Package weight/volume")
    time_window_start: Optional[str] = None  # HH:MM format
    time_window_end: Optional[str] = None
    service_time: int = Field(default=5, ge=0, description="Minutes at stop")
    priority: int = Field(default=1, ge=1, le=3, description="1=high, 3=low")


class Vehicle(BaseModel):
    id: str
    name: Optional[str] = None
    capacity: float = Field(default=100.0, gt=0)
    max_stops: Optional[int] = Field(default=None, ge=1)
    start_time: str = Field(default="08:00")
    end_time: str = Field(default="18:00")
    speed_factor: float = Field(default=1.0, gt=0, description="Relative speed")


class OptimizationObjective(str, Enum):
    MINIMIZE_DISTANCE = "minimize_distance"
    MINIMIZE_TIME = "minimize_time"
    BALANCE_ROUTES = "balance_routes"


class OptimizationRequest(BaseModel):
    depot: Depot
    deliveries: list[Delivery]
    vehicles: list[Vehicle]
    objective: OptimizationObjective = OptimizationObjective.MINIMIZE_DISTANCE
    max_computation_time: int = Field(default=30, ge=1, le=300, description="Seconds")


class RouteStop(BaseModel):
    sequence: int
    delivery_id: str
    location: LocationBase
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None
    cumulative_distance: float
    cumulative_load: float


class Route(BaseModel):
    vehicle_id: str
    vehicle_name: Optional[str] = None
    stops: list[RouteStop]
    total_distance: float  # in kilometers
    total_time: int  # in minutes
    total_load: float
    utilization: float  # percentage of capacity used


class OptimizationResult(BaseModel):
    success: bool
    message: str
    routes: list[Route]
    unassigned_deliveries: list[str]
    total_distance: float
    total_time: int
    computation_time: float  # seconds


class UploadResponse(BaseModel):
    success: bool
    message: str
    deliveries_count: int = 0
    deliveries: list[Delivery] = []


class HealthResponse(BaseModel):
    status: str
    version: str
