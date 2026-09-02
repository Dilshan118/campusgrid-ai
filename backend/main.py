"""
CampusGrid AI: FastAPI Backend Entry Point
Provides REST API endpoints and WebSocket channels for the React Single Page Application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="CampusGrid AI API",
    description="Decoupled Multi-Agent Microgrid Energy Management System & Cyber-Physical Digital Twin",
    version="4.2.0"
)

# Enable CORS for React Frontend (running on port 5173 by default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
    """Simple health check endpoint."""
    return {
        "status": "online",
        "system": "CampusGrid AI Microgrid Platform",
        "version": "4.2.0"
    }

# Note: Sub-routers for telemetry, optimization, simulation, agents, and analytics
# will be registered here as team members complete their modules.
