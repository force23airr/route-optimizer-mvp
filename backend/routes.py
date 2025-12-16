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
    CompanySettings,
    RouteHistoryEntry,
)
from cuopt_service import get_cuopt_service, MockCuOptService
import json
import os
import uuid
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

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
                    phone=row.get("phone", "").strip() or None,
                    notes=row.get("notes", "").strip() or None,
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


HISTORY_DIR = os.path.join(os.path.dirname(__file__), "route_history")
os.makedirs(HISTORY_DIR, exist_ok=True)


class PDFExportRequest(BaseModel):
    routes: list[Route]
    depot: Depot
    cost_settings: Optional[CostSettings] = None
    company: Optional[CompanySettings] = None


@router.post("/export/pdf")
async def export_routes_pdf(request: PDFExportRequest):
    """
    Export optimized routes as a PDF document with driver route sheets.
    Each route gets its own page with turn-by-turn stop list.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()

    company_style = ParagraphStyle(
        'CompanyHeader',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=4,
        textColor=colors.HexColor('#1976d2'),
    )

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

    small_style = ParagraphStyle(
        'SmallText',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
    )

    elements = []

    for route_idx, route in enumerate(request.routes):
        if route_idx > 0:
            elements.append(PageBreak())

        # Company header
        if request.company:
            elements.append(Paragraph(request.company.name, company_style))
            if request.company.address:
                elements.append(Paragraph(request.company.address, small_style))
            if request.company.phone:
                elements.append(Paragraph(f"Phone: {request.company.phone}", small_style))
            elements.append(Spacer(1, 0.2*inch))

        # Route header
        vehicle_name = route.vehicle_name or route.vehicle_id
        elements.append(Paragraph(f"Driver Route Sheet: {vehicle_name}", title_style))
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", small_style))
        elements.append(Spacer(1, 0.1*inch))

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

        # Detailed stop list with customer info and directions
        elements.append(Paragraph("Stop Details:", subtitle_style))

        for stop in route.stops:
            stop_miles = stop.cumulative_distance * 0.621371

            # Stop header
            stop_header = f"Stop {stop.sequence}: {stop.delivery_id}"
            if stop.customer_name:
                stop_header = f"Stop {stop.sequence}: {stop.customer_name} ({stop.delivery_id})"
            elements.append(Paragraph(f"<b>{stop_header}</b>", styles['Normal']))

            # Directions
            if stop.directions:
                elements.append(Paragraph(f"<i>Directions: {stop.directions}</i>", small_style))

            # Address and contact
            if stop.location.address:
                elements.append(Paragraph(f"Address: {stop.location.address}", styles['Normal']))
            if stop.customer_phone:
                elements.append(Paragraph(f"Phone: {stop.customer_phone}", styles['Normal']))

            # Times
            time_info = f"Arrival: {stop.arrival_time or '-'} | Departure: {stop.departure_time or '-'} | Distance: {stop_miles:.1f} mi"
            elements.append(Paragraph(time_info, small_style))
            elements.append(Spacer(1, 0.1*inch))

        # Return to depot
        elements.append(Spacer(1, 0.1*inch))
        elements.append(Paragraph("End: Return to Depot", subtitle_style))

    doc.build(elements)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=route_sheets.pdf"}
    )


class EmailRouteRequest(BaseModel):
    routes: list[Route]
    depot: Depot
    cost_settings: Optional[CostSettings] = None
    company: Optional[CompanySettings] = None
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str
    smtp_password: str
    from_email: str
    driver_emails: dict[str, str]  # vehicle_id -> email


@router.post("/export/email")
async def email_route_sheets(request: EmailRouteRequest):
    """
    Email route sheets directly to drivers.
    Requires SMTP configuration and driver email addresses.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    sent_count = 0
    errors = []

    for route in request.routes:
        driver_email = request.driver_emails.get(route.vehicle_id)
        if not driver_email:
            continue

        # Generate PDF for this route
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Company header
        if request.company:
            elements.append(Paragraph(request.company.name, styles['Heading1']))

        vehicle_name = route.vehicle_name or route.vehicle_id
        elements.append(Paragraph(f"Route Sheet: {vehicle_name}", styles['Heading2']))
        elements.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", styles['Normal']))
        elements.append(Spacer(1, 0.2*inch))

        # Stops
        for stop in route.stops:
            stop_text = f"Stop {stop.sequence}: {stop.customer_name or stop.delivery_id}"
            if stop.location.address:
                stop_text += f" - {stop.location.address}"
            if stop.customer_phone:
                stop_text += f" (Phone: {stop.customer_phone})"
            elements.append(Paragraph(stop_text, styles['Normal']))
            if stop.directions:
                elements.append(Paragraph(f"  Directions: {stop.directions}", styles['Italic']))

        doc.build(elements)
        buffer.seek(0)

        # Send email
        try:
            msg = MIMEMultipart()
            msg['From'] = request.from_email
            msg['To'] = driver_email
            msg['Subject'] = f"Route Sheet - {vehicle_name} - {datetime.now().strftime('%Y-%m-%d')}"

            body = f"Please find your route sheet attached for {datetime.now().strftime('%Y-%m-%d')}.\n\nTotal Stops: {len(route.stops)}\nTotal Distance: {route.total_distance:.1f} km"
            msg.attach(MIMEText(body, 'plain'))

            part = MIMEBase('application', 'octet-stream')
            part.set_payload(buffer.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="route_sheet_{route.vehicle_id}.pdf"')
            msg.attach(part)

            server = smtplib.SMTP(request.smtp_host, request.smtp_port)
            server.starttls()
            server.login(request.smtp_username, request.smtp_password)
            server.send_message(msg)
            server.quit()
            sent_count += 1
        except Exception as e:
            errors.append(f"{vehicle_name}: {str(e)}")

    return {
        "success": len(errors) == 0,
        "sent_count": sent_count,
        "errors": errors
    }


class SaveHistoryRequest(BaseModel):
    depot: Depot
    routes: list[Route]
    total_distance: float
    total_time: int
    total_cost: Optional[float] = None


@router.post("/history/save")
async def save_route_history(request: SaveHistoryRequest):
    """Save optimization result to history for reporting."""
    entry_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().isoformat()

    entry = RouteHistoryEntry(
        id=entry_id,
        timestamp=timestamp,
        depot=request.depot,
        total_deliveries=sum(len(r.stops) for r in request.routes),
        total_routes=len(request.routes),
        total_distance=request.total_distance,
        total_time=request.total_time,
        total_cost=request.total_cost,
        routes=request.routes
    )

    filepath = os.path.join(HISTORY_DIR, f"{entry_id}.json")
    with open(filepath, 'w') as f:
        f.write(entry.model_dump_json(indent=2))

    return {"success": True, "id": entry_id, "timestamp": timestamp}


@router.get("/history")
async def get_route_history():
    """Get all saved route history entries."""
    entries = []
    for filename in os.listdir(HISTORY_DIR):
        if filename.endswith('.json'):
            filepath = os.path.join(HISTORY_DIR, filename)
            with open(filepath, 'r') as f:
                data = json.load(f)
                # Return summary without full route details
                entries.append({
                    "id": data["id"],
                    "timestamp": data["timestamp"],
                    "total_deliveries": data["total_deliveries"],
                    "total_routes": data["total_routes"],
                    "total_distance": data["total_distance"],
                    "total_time": data["total_time"],
                    "total_cost": data.get("total_cost"),
                })
    entries.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"entries": entries}


@router.get("/history/{entry_id}")
async def get_route_history_entry(entry_id: str):
    """Get a specific route history entry with full details."""
    filepath = os.path.join(HISTORY_DIR, f"{entry_id}.json")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="History entry not found")
    with open(filepath, 'r') as f:
        return json.load(f)


@router.delete("/history/{entry_id}")
async def delete_route_history_entry(entry_id: str):
    """Delete a route history entry."""
    filepath = os.path.join(HISTORY_DIR, f"{entry_id}.json")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="History entry not found")
    os.remove(filepath)
    return {"success": True}
