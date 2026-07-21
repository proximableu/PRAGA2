"""FastAPI route handlers implementing OpenAI-compatible gateway endpoints."""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.models import ChatRequest, ModelInfo, ModelListResponse
from config import settings
from database.router import DatabaseRouter
from services.execution import ExecutionService
from services.routing import RoutingResolutionService

router = APIRouter(prefix="/v1", tags=["OpenAI Compatible"])


def get_db_router(request: Request) -> DatabaseRouter:
    """Dependency helper to safely retrieve DatabaseRouter from app state."""
    if not hasattr(request.app.state, "db_router"):
        raise HTTPException(
            status_code=500,
            detail="DatabaseRouter is not initialized on app.state",
        )
    return request.app.state.db_router


@router.post("/chat/completions")
async def chat_completions(
    request: ChatRequest,
    db_router: DatabaseRouter = Depends(get_db_router),
    routing_service: RoutingResolutionService = Depends(),
) -> StreamingResponse:
    """Primary ingestion endpoint.

    Validates payloads, resolves routing context, and streams agentic
    execution telemetry via SSE.
    """
    # 1. Resolve Target Database & LLM
    rag_db = getattr(request, "rag_db", None)
    ctx = routing_service.resolve(request.model, rag_db)

    # 2. Extract messages cleanly whether dict or object
    formatted_messages = []
    for m in request.messages:
        if isinstance(m, dict):
            formatted_messages.append(
                {"role": m.get("role", "user"), "content": m.get("content", "")}
            )
        else:
            formatted_messages.append(
                {
                    "role": getattr(m, "role", "user"),
                    "content": getattr(m, "content", ""),
                }
            )

    # 3. Initialize Execution Service with the injected DatabaseRouter instance
    exec_service = ExecutionService(db_router=db_router)

    return StreamingResponse(
        content=exec_service.execute_request(
            routing_ctx=ctx,
            messages=formatted_messages,
            params={
                "temperature": getattr(request, "temperature", 0.7),
                "max_tokens": getattr(request, "max_tokens", None),
            },
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disables proxy buffering in Nginx
        },
    )


@router.get("/models")
async def list_models() -> ModelListResponse:
    """Dynamically generates available model aliases from configuration registries."""
    models: List[ModelInfo] = []

    # Map available models
    model_db_map = getattr(settings, "MODEL_DB_MAP", {})
    if isinstance(model_db_map, dict):
        for alias in model_db_map.keys():
            models.append(ModelInfo(id=alias))

    # Map available RAG databases
    rag_registry = getattr(settings, "RAG_DB_REGISTRY", {})
    if isinstance(rag_registry, dict):
        for db_name in rag_registry.values():
            rag_alias = f"RAG:{db_name}"
            if rag_alias not in [m.id for m in models]:
                models.append(ModelInfo(id=rag_alias))

    return ModelListResponse(data=models)


@router.get("/debug/retrieved/view")
async def debug_retrieved_view() -> Dict[str, Any]:
    """Backward compatibility endpoint serving diagnostic retrieval logs."""
    return {
        "status": "active",
        "latest_context_log": [],
        "message": "Diagnostic endpoint operational. Awaiting Phase 4 telemetry injection.",
    }