from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.core.database import get_db
from app.models.notification import Notification, NotificationStatus
from app.schemas.notification import NotificationResponse

router = APIRouter(prefix="/dlq", tags=["dlq"])


@router.get("", response_model=List[NotificationResponse])
async def list_dlq(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification)
        .where(Notification.status == NotificationStatus.dead_lettered)
        .order_by(Notification.failed_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.post("/{notification_id}/retry",
             response_model=NotificationResponse)
async def retry_dlq(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id)
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.status != NotificationStatus.dead_lettered:
        raise HTTPException(
            status_code=400,
            detail="Only dead_lettered notifications can be retried"
        )

    notification.status = NotificationStatus.pending
    notification.retry_count = 0
    notification.error_message = None

    from app.workers.email_worker import deliver_email
    from app.workers.websocket_worker import deliver_websocket
    from app.workers.webhook_worker import deliver_webhook
    from app.models.notification import NotificationChannel

    task_map = {
        NotificationChannel.email: deliver_email,
        NotificationChannel.websocket: deliver_websocket,
        NotificationChannel.webhook: deliver_webhook,
    }
    task_map[notification.channel].apply_async(args=[notification.id])
    notification.status = NotificationStatus.queued

    await db.commit()
    await db.refresh(notification)
    return notification


@router.delete("/{notification_id}",
               status_code=204)
async def discard_dlq(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id)
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.delete(notification)
    await db.commit()