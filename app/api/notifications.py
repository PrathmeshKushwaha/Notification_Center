import uuid
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis

from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_current_user
from app.models.notification import Notification, NotificationStatus, NotificationChannel
from app.models.preference import UserPreference
from app.schemas.notification import (
    NotificationCreate, NotificationResponse, NotificationStatusResponse
)

router = APIRouter(prefix="/notify", tags=["notifications"])


async def get_redis():
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


@router.post("", status_code=status.HTTP_202_ACCEPTED,
             response_model=NotificationResponse)
async def send_notification(
    payload: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    # Idempotency check
    if payload.idempotency_key:
        cached = await redis.get(f"idem:{payload.idempotency_key}")
        if cached:
            result = await db.execute(
                select(Notification).where(Notification.id == cached)
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing

    # Preference check
    pref_result = await db.execute(
        select(UserPreference).where(
            UserPreference.user_id == payload.user_id
        )
    )
    pref = pref_result.scalar_one_or_none()

    if pref:
        channel_map = {
            NotificationChannel.email: pref.email_enabled,
            NotificationChannel.websocket: pref.websocket_enabled,
            NotificationChannel.webhook: pref.webhook_enabled,
        }
        if not channel_map.get(payload.channel, True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User has disabled {payload.channel} notifications"
            )

    # Create notification
    notification = Notification(
        id=str(uuid.uuid4()),
        user_id=payload.user_id,
        channel=payload.channel,
        priority=payload.priority,
        status=NotificationStatus.pending,
        template_id=payload.template_id,
        variables=payload.variables,
        idempotency_key=payload.idempotency_key,
    )
    db.add(notification)
    await db.flush()

    try:
        if payload.channel == NotificationChannel.email:
            from app.workers.email_worker import deliver_email as task
        elif payload.channel == NotificationChannel.websocket:
            from app.workers.websocket_worker import deliver_websocket as task
        elif payload.channel == NotificationChannel.webhook:
            from app.workers.webhook_worker import deliver_webhook as task

        priority_map = {"critical": 10, "high": 7, "normal": 5, "low": 1}
        task.apply_async(
            args=[notification.id],
            priority=priority_map.get(payload.priority, 5)
        )

        notification.status = NotificationStatus.queued
        notification.queued_at = datetime.utcnow()

    except Exception as e:
        notification.status = NotificationStatus.failed
        notification.error_message = str(e)

    await db.commit()
    await db.refresh(notification)

    # Store idempotency key
    if payload.idempotency_key:
        await redis.setex(
            f"idem:{payload.idempotency_key}",
            86400,
            notification.id
        )

    return notification


@router.get("/{notification_id}/status",
            response_model=NotificationStatusResponse)
async def get_notification_status(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id)
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    return notification


@router.get("/history", response_model=List[NotificationResponse])
async def get_history(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()