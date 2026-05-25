from typing import Any

from mcp.server.fastmcp import FastMCP

from factroll.core import engine
from factroll.mcp.auth import current_surface_id, current_user_id

mcp = FastMCP(
    "factroll",
    instructions=(
        "Factroll: guided fact-rolling sessions. "
        "Call with action='start' and {topic} to begin. "
        "Subsequent valid actions are returned in each response."
    ),
)


@mcp.tool(
    description=(
        "Factroll: guided fact-rolling sessions. "
        "Call with action='start' and {topic} to begin. "
        "Subsequent valid actions are returned in each response."
    )
)
async def factroll(action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    user_id = current_user_id.get()
    surface_id = current_surface_id.get()
    result = engine.handle_action(user_id, surface_id, action, params)
    response: dict[str, Any] = {"say": result.say, "next_actions": result.next_actions}
    if result.state is not None:
        response["state"] = result.state
    return response
