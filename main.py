"""FastAPI application instantiation, lifespan management, and dependency wiring."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from database.router import DatabaseRouter
from services.routing import RoutingResolutionService
from api.endpoints import router as api_router
from config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Orchestrates application startup and graceful shutdown.
    Logs routing aliases, agentic configuration, and disposes connection pools.
    """
    # Startup: Initialize routing infrastructure
    db_router = DatabaseRouter()
    app.state.db_router = db_router

    registered_aliases = len(settings.MODEL_DB_MAP) + len(settings.RAG_DB_REGISTRY)
    print(f"[Gateway] Initialized. Registered {registered_aliases} routing aliases.")
    print(f"[Gateway] Agentic Config: Max Turns={settings.AGENT_MAX_TURNS}, "
          f"Telemetry={settings.ENABLE_REASONING_TELEMETRY}, Audit={settings.ENABLE_AUDIT_FOOTER}")

    yield  # Application runs here

    # Shutdown: Dispose connection pools to prevent leaks
    await db_router.dispose_pools()
    print("[Gateway] Connection pools disposed. Shutdown complete.")


# Instantiate FastAPI with lifespan and OpenAPI metadata
app = FastAPI(
    title="Local RAG Gateway",
    description="OpenAI-compatible API gateway with dynamic PostgreSQL routing & agentic streaming.",
    version="4.0.0",
    lifespan=lifespan
)

# Global dependency overrides for clean injection
app.dependency_overrides[DatabaseRouter] = lambda: app.state.db_router
app.dependency_overrides[RoutingResolutionService] = lambda: RoutingResolutionService()

# Mount API routes
app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "phase": 4}