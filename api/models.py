"""Pydantic v2 schemas enforcing OpenAI-compatible request/response contracts."""
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    model: Optional[str] = None
    messages: List[Message]
    rag_db: Optional[str] = None  # Explicit override parameter [3]
    stream: bool = False
    temperature: float = 0.7
    max_tokens: Optional[int] = None

class ChatChoice(BaseModel):
    index: int
    message: Message
    finish_reason: Optional[Literal["stop", "length"]] = None

class ChatCompletionResponse(BaseModel):
    id: str = Field(default="chatcmpl-rag-gateway")
    object: str = Field(default="chat.completion")
    created: int = Field(default=1700000000)
    model: str
    choices: List[ChatChoice]

class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int = 1700000000
    owned_by: str = "rag-gateway"

class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelInfo]