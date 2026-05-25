from typing import Any
from pydantic import BaseModel


class ToolRequest(BaseModel):
    action: str
    params: dict[str, Any] | None = None


class ToolResponseSchema(BaseModel):
    say: str
    next_actions: list[str]
    state: dict[str, Any] | None = None
