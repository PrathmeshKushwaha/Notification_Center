import logging
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from contextlib import asynccontextmanager
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from app.core.config import settings
from app.core.database import engine
from app.core.metrics import active_websocket_connections, get_metrics
from app.api import notifications, templates, preferences, dlq
from app.channels.websocket import manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def redis_listener_wrapper():
    while True:
        try:
            logger.info("Redis listener starting...")
            await manager.start_listener()
        except Exception as e:
            logger.error(f"Redis listener crashed: {e}, restarting in 3s")
            await asyncio.sleep(3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("App startup — launching Redis listener")
    task = asyncio.create_task(redis_listener_wrapper())
    app.state.listener_task = task
    yield
    logger.info("App shutdown — cancelling Redis listener")
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notifications.router)
app.include_router(templates.router)
app.include_router(preferences.router)
app.include_router(dlq.router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "ws_connections": len(manager.active)
    }


@app.get("/metrics")
async def metrics():
    return Response(
        content=get_metrics(),
        media_type=CONTENT_TYPE_LATEST
    )

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    active_websocket_connections.inc()
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id)
        active_websocket_connections.dec()