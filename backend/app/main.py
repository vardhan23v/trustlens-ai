"""TrustLens AI backend. Frontend → FastAPI → CrewAI/Gemini (the browser never talks to Gemini)."""
import logging
import os

from app.config import FRONTEND_DIST, settings  # first: disables CrewAI telemetry before crewai is imported

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes import analyze, demos, health

logging.basicConfig(level=logging.DEBUG if settings.DEBUG else logging.INFO)

app = FastAPI(title="TrustLens AI", version="1.0.0")

origins = ["http://localhost:5173"]
if os.getenv("RAILWAY_PUBLIC_DOMAIN"):
    origins.append(f"https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["*"])

for r in (health.router, analyze.router, demos.router):
    app.include_router(r, prefix="/api")

# Production (Railway): serve the built frontend from the same origin, after the /api routes.
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
