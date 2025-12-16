# Route Optimizer MVP

A delivery route optimization application with a FastAPI backend and Next.js frontend.

## Features

- Upload delivery locations via CSV
- Configure depot location and vehicle fleet
- Optimize routes using nearest-neighbor heuristic (mock cuOpt)
- Visualize routes on an interactive map
- Support for time windows, vehicle capacity, and multiple objectives

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- (Optional) Docker & Docker Compose

### Option 1: Run Locally

**Backend:**

```bash
cd backend
pip install -r requirements.txt
python main.py
```

Backend runs at http://localhost:8000

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:3000

### Option 2: Run with Docker

```bash
docker-compose up --build
```

## CSV Format

Upload a CSV file with delivery locations:

| Column | Required | Description |
|--------|----------|-------------|
| id | Yes | Unique delivery ID |
| latitude | Yes | Decimal latitude |
| longitude | Yes | Decimal longitude |
| name | No | Customer/delivery name |
| address | No | Street address |
| demand | No | Package weight/volume (default: 1) |
| time_window_start | No | Earliest arrival (HH:MM) |
| time_window_end | No | Latest arrival (HH:MM) |
| service_time | No | Minutes at stop (default: 5) |
| priority | No | 1-3, lower = higher priority |

Example:

```csv
id,name,latitude,longitude,address,demand
d1,Customer A,37.7749,-122.4194,123 Main St,10
d2,Customer B,37.7849,-122.4094,456 Oak Ave,15
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/health | Health check |
| POST | /api/upload | Upload CSV file |
| POST | /api/optimize | Run optimization |
| GET | /api/sample-data | Get sample data |

## Configuration

### Backend (.env)

```
HOST=0.0.0.0
PORT=8000
DEBUG=true
CORS_ORIGINS=http://localhost:3000
CUOPT_API_KEY=  # Optional: Add for real cuOpt
```

### Optimization Objectives

- **minimize_distance**: Shortest total travel distance
- **minimize_time**: Fastest completion time
- **balance_routes**: Even distribution across vehicles

## Integrating Real cuOpt

To use NVIDIA cuOpt instead of the mock optimizer:

1. Get API credentials from [NVIDIA NGC](https://ngc.nvidia.com/)
2. Set `CUOPT_API_KEY` in backend/.env
3. Implement `_call_cuopt_api()` in `cuopt_service.py`

## Tech Stack

- **Backend**: FastAPI, Pydantic, uvicorn
- **Frontend**: Next.js 14, React 18, TypeScript
- **Map**: Leaflet, react-leaflet
- **File Upload**: react-dropzone

## License

MIT
