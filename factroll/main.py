from fastapi import FastAPI

from factroll.mcp.auth import auth_middleware
from factroll.mcp.server import mcp

app = FastAPI(title="Factroll MCP Server")
app.middleware("http")(auth_middleware)

mcp_asgi = mcp.streamable_http_app()
app.mount("/mcp", mcp_asgi)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
