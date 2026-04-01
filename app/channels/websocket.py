import json
import logging
import asyncio
from typing import Dict
from fastapi import WebSocket
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active[user_id] = websocket
        logger.info(f"WS connected: {user_id}")

    def disconnect(self, user_id: str):
        self.active.pop(user_id, None)
        logger.info(f"WS disconnected: {user_id}")

    async def send_to_user(self, user_id: str, message: dict) -> bool:
        websocket = self.active.get(user_id)
        if websocket:
            try:
                await websocket.send_json(message)
                logger.info(f"WS pushed to {user_id}")
                return True
            except Exception as e:
                logger.error(f"WS send failed for {user_id}: {e}")
                self.disconnect(user_id)
        return False

    async def publish(self, user_id: str, message: dict):
        redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            await redis.publish(f"ws:{user_id}", json.dumps(message))
            logger.info(f"Published to Redis ws:{user_id}")
        finally:
            await redis.aclose()

    async def start_listener(self):
        logger.info("Starting Redis pub/sub listener")
        redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        pubsub = redis.pubsub()
        await pubsub.psubscribe("ws:*")
        logger.info("Subscribed to ws:* channels")
        try:
            async for message in pubsub.listen():
                if message["type"] == "pmessage":
                    try:
                        user_id = message["channel"].split(":", 1)[1]
                        data = json.loads(message["data"])
                        await self.send_to_user(user_id, data)
                    except Exception as e:
                        logger.error(f"Listener error: {e}")
        except asyncio.CancelledError:
            logger.info("Redis listener cancelled")
        finally:
            await pubsub.unsubscribe()
            await redis.aclose()


manager = ConnectionManager()