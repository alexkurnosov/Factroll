from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionState:
    session_id: str
    user_id: str
    surface_id: str
    topic: str
    el: float
    fact_count: int

    def as_hint(self) -> dict[str, Any]:
        return {"topic": self.topic, "el": self.el, "fact_count": self.fact_count}


@dataclass
class ToolResponse:
    say: str
    next_actions: list[str]
    state: dict[str, Any] | None = None
