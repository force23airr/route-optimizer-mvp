"""
Route Optimizer MVP - FastAPI Backend
"""

import os
from pathlib import Path
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routes import router

# Load environment variables (relative to this file, not the current working directory)
env_dir = Path(__file__).resolve().parent
load_dotenv(env_dir / ".env.local")
load_dotenv(env_dir / ".env")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    print("Starting Route Optimizer API...")
    try:
        api_paths = sorted({getattr(r, "path", "") for r in app.routes if getattr(r, "path", "").startswith("/api/")})
        logger.info("Registered API routes: %s", ", ".join(api_paths))
    except Exception:
        logger.exception("Failed to enumerate routes at startup")
    yield
    print("Shutting down Route Optimizer API...")


app = FastAPI(
    title="Route Optimizer API",
    description="Delivery route optimization service using cuOpt",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Route Optimizer API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )
