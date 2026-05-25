"""
Core engine — Milestone 0 stubs.

All methods return in-memory fixtures. Real DB-backed logic starts in Milestone 1.
The surface layer (MCP adapter) must not import anything from factroll.mcp or factroll.db.
"""
import uuid
from factroll.core.models import SessionState, ToolResponse

# In-memory session store keyed by (user_id, surface_id).
# Replaced by Postgres in Milestone 1.
_sessions: dict[tuple[str, str], SessionState] = {}

_IDLE_ACTIONS = ["start"]
_ACTIVE_ACTIONS = ["next_fact", "switch_topic", "set_experience_level", "end_session"]


def start_session(user_id: str, surface_id: str, topic: str) -> ToolResponse:
    session = SessionState(
        session_id=str(uuid.uuid4()),
        user_id=user_id,
        surface_id=surface_id,
        topic=topic,
        el=0.0,
        fact_count=0,
    )
    _sessions[(user_id, surface_id)] = session
    return ToolResponse(
        say=f"Session started on '{topic}' at EL 0%. Ready to roll facts.",
        next_actions=_ACTIVE_ACTIONS,
        state=session.as_hint(),
    )


def end_session(user_id: str, surface_id: str) -> ToolResponse:
    _sessions.pop((user_id, surface_id), None)
    return ToolResponse(
        say="Session ended. Your progress has been saved.",
        next_actions=_IDLE_ACTIONS,
    )


def get_session(user_id: str, surface_id: str) -> SessionState | None:
    return _sessions.get((user_id, surface_id))


def handle_action(user_id: str, surface_id: str, action: str, params: dict | None) -> ToolResponse:
    params = params or {}

    if action == "start":
        topic = params.get("topic", "general")
        return start_session(user_id, surface_id, topic)

    if action == "end_session":
        return end_session(user_id, surface_id)

    session = get_session(user_id, surface_id)
    if session is None:
        return ToolResponse(
            say="No active session. Start one first.",
            next_actions=_IDLE_ACTIONS,
        )

    # Remaining actions are stubs until Milestone 1.
    return ToolResponse(
        say=f"Action '{action}' is not yet implemented (Milestone 0).",
        next_actions=_ACTIVE_ACTIONS,
        state=session.as_hint(),
    )
