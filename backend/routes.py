"""
API Routes for Route Optimizer
"""

import csv
import io
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from models import (
    Delivery,
    Depot,
    Vehicle,
    OptimizationRequest,
    OptimizationResult,
    UploadResponse,
    HealthResponse,
    OptimizationObjective,
    Route,
    CostSettings,
)
from cuopt_service import get_cuopt_service, MockCuOptService

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="1.0.0")


@router.post("/upload", response_model=UploadResponse)
async def upload_deliveries(file: UploadFile = File(...)):
    """
    Upload a CSV file with delivery locations.

    Expected CSV columns:
    - id: Unique identifier
    - name: Optional delivery name
    - latitude: Decimal latitude
    - longitude: Decimal longitude
    - address: Optional address string
    - demand: Optional package weight/volume (default: 1)
    - time_window_start: Optional HH:MM
    - time_window_end: Optional HH:MM
    - service_time: Optional minutes at stop (default: 5)
    - priority: Optional 1-3 (default: 1)
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    try:
        contents = await file.read()
        decoded = contents.decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded))

        deliveries: list[Delivery] = []

        for row_num, row in enumerate(reader, start=2):
            try:
                # Required fields
                if "id" not in row or not row["id"]:
                    row["id"] = f"delivery_{row_num}"

                if "latitude" not in row or "longitude" not in row:
                    raise ValueError(f"Row {row_num}: latitude and longitude are required")

                delivery = Delivery(
                    id=row["id"].strip(),
                    name=row.get("name", "").strip() or None,
                    latitude=float(row["latitude"]),
                    longitude=float(row["longitude"]),
                    address=row.get("address", "").strip() or None,
                    demand=float(row.get("demand", 1)) if row.get("demand") else 1.0,
                    time_window_start=row.get("time_window_start", "").strip() or None,
                    time_window_end=row.get("time_window_end", "").strip() or None,
                    service_time=int(row.get("service_time", 5)) if row.get("service_time") else 5,
                    priority=int(row.get("priority", 1)) if row.get("priority") else 1,
                )
                deliveries.append(delivery)

            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Error parsing row {row_num}: {str(e)}"
                )

        if not deliveries:
            raise HTTPException(status_code=400, detail="No valid deliveries found in file")

        return UploadResponse(
            success=True,
            message=f"Successfully parsed {len(deliveries)} deliveries",
            deliveries_count=len(deliveries),
            deliveries=deliveries
        )

    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/optimize", response_model=OptimizationResult)
async def optimize_routes(
    request: OptimizationRequest,
    service: MockCuOptService = Depends(get_cuopt_service)
):
    """
    Run route optimization on the provided data.

    Requires:
    - depot: Starting location for all vehicles
    - deliveries: List of delivery locations
    - vehicles: List of available vehicles

    Optional:
    - objective: minimize_distance, minimize_time, or balance_routes
    - max_computation_time: Maximum seconds to spend optimizing
    """
    if not request.deliveries:
        raise HTTPException(status_code=400, detail="At least one delivery is required")

    if not request.vehicles:
        raise HTTPException(status_code=400, detail="At least one vehicle is required")

    try:
        result = service.optimize(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")


@router.post("/optimize/quick", response_model=OptimizationResult)
async def quick_optimize(
    depot_lat: float,
    depot_lon: float,
    file: UploadFile = File(...),
    num_vehicles: int = 3,
    vehicle_capacity: float = 100.0,
    objective: OptimizationObjective = OptimizationObjective.MINIMIZE_DISTANCE,
    service: MockCuOptService = Depends(get_cuopt_service)
):
    """
    Quick optimization endpoint - upload CSV and get results in one call.

    This is a convenience endpoint that combines upload and optimize.
    """
    # First upload and parse the file
    upload_result = await upload_deliveries(file)

    if not upload_result.success:
        raise HTTPException(status_code=400, detail=upload_result.message)

    # Create default vehicles
    vehicles = [
        Vehicle(
            id=f"vehicle_{i+1}",
            name=f"Vehicle {i+1}",
            capacity=vehicle_capacity
        )
        for i in range(num_vehicles)
    ]

    # Create optimization request
    request = OptimizationRequest(
        depot=Depot(latitude=depot_lat, longitude=depot_lon),
        deliveries=upload_result.deliveries,
        vehicles=vehicles,
        objective=objective
    )

    # Run optimization
    return service.optimize(request)


@router.get("/sample-data")
async def get_sample_data():
    """
    Get sample delivery data for testing.

    Returns sample deliveries in the San Francisco area.
    """
    sample_deliveries = [
        Delivery(id="d1", name="Customer A", latitude=37.7749, longitude=-122.4194, address="Downtown SF", demand=10),
        Delivery(id="d2", name="Customer B", latitude=37.7849, longitude=-122.4094, address="North Beach", demand=15),
        Delivery(id="d3", name="Customer C", latitude=37.7649, longitude=-122.4294, address="Mission District", demand=8),
        Delivery(id="d4", name="Customer D", latitude=37.7549, longitude=-122.4394, address="Castro", demand=12),
        Delivery(id="d5", name="Customer E", latitude=37.7899, longitude=-122.4044, address="Fisherman's Wharf", demand=20),
        Delivery(id="d6", name="Customer F", latitude=37.7699, longitude=-122.4494, address="Sunset", demand=5),
        Delivery(id="d7", name="Customer G", latitude=37.7799, longitude=-122.3994, address="Embarcadero", demand=18),
        Delivery(id="d8", name="Customer H", latitude=37.7599, longitude=-122.4144, address="Noe Valley", demand=7),
    ]

    sample_depot = Depot(
        latitude=37.7749,
        longitude=-122.4194,
        address="Warehouse - Market St"
    )

    sample_vehicles = [
        Vehicle(id="v1", name="Van 1", capacity=50),
        Vehicle(id="v2", name="Van 2", capacity=50),
        Vehicle(id="v3", name="Truck 1", capacity=100),
    ]

    return {
        "depot": sample_depot,
        "deliveries": sample_deliveries,
        "vehicles": sample_vehicles
    }


class PDFExportRequest(BaseModel):
    routes: list[Route]
    depot: Depot
    cost_settings: Optional[CostSettings] = None


@router.post("/export/pdf")
async def export_routes_pdf(request: PDFExportRequest):
    """
    Export optimized routes as a PDF document with driver route sheets.
    Each route gets its own page with turn-by-turn stop list.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=12,
    )

    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=8,
    )

    elements = []

    for route_idx, route in enumerate(request.routes):
        if route_idx > 0:
            elements.append(Spacer(1, 0.5*inch))

        # Route header
        vehicle_name = route.vehicle_name or route.vehicle_id
        elements.append(Paragraph(f"Driver Route Sheet: {vehicle_name}", title_style))

        # Route summary
        total_miles = route.total_distance * 0.621371  # km to miles
        summary_data = [
            ["Total Stops", str(len(route.stops))],
            ["Total Distance", f"{total_miles:.1f} miles ({route.total_distance:.1f} km)"],
            ["Total Time", f"{route.total_time} minutes"],
            ["Load / Utilization", f"{route.total_load} units ({route.utilization}%)"],
        ]

        if request.cost_settings:
            distance_cost = total_miles * request.cost_settings.cost_per_mile
            time_cost = (route.total_time / 60) * request.cost_settings.cost_per_hour
            route_cost = distance_cost + time_cost
            summary_data.append(["Estimated Cost", f"${route_cost:.2f}"])

        summary_table = Table(summary_data, colWidths=[1.5*inch, 3*inch])
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 0.25*inch))

        # Depot start
        elements.append(Paragraph("Start: Depot", subtitle_style))
        depot_info = f"Location: ({request.depot.latitude:.4f}, {request.depot.longitude:.4f})"
        if request.depot.address:
            depot_info = f"Address: {request.depot.address}"
        elements.append(Paragraph(depot_info, styles['Normal']))
        elements.append(Spacer(1, 0.15*inch))

        # Stop list
        elements.append(Paragraph("Stop Sequence:", subtitle_style))

        stop_data = [["#", "ID", "Arrival", "Departure", "Distance", "Load"]]
        for stop in route.stops:
            stop_miles = stop.cumulative_distance * 0.621371
            stop_data.append([
                str(stop.sequence),
                stop.delivery_id,
                stop.arrival_time or "-",
                stop.departure_time or "-",
                f"{stop_miles:.1f} mi",
                f"{stop.cumulative_load}",
            ])

        stop_table = Table(stop_data, colWidths=[0.4*inch, 1.2*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.7*inch])
        stop_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(stop_table)
        elements.append(Spacer(1, 0.15*inch))

        # Return to depot
        elements.append(Paragraph("End: Return to Depot", subtitle_style))

    doc.build(elements)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=route_sheets.pdf"}
    )
