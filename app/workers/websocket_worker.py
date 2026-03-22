import logging
import json
from datetime import datetime
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.workers.websocket_worker.deliver_websocket",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    queue="websocket_queue",
)
def deliver_websocket(self, notification_id: str):
    import redis
    from app.core.database import get_sync_db
    from app.models.notification import Notification, NotificationStatus
    from app.core.config import settings

    db = get_sync_db()
    try:
        notification = db.get(Notification, notification_id)
        if not notification:
            return

        if notification.status == NotificationStatus.delivered:
            return

        notification.status = NotificationStatus.in_flight
        db.commit()

        message = {
            "id": notification.id,
            "channel": notification.channel,
            "variables": notification.variables,
            "created_at": str(notification.created_at),
        }

        # Publish to Redis pub/sub sync
        r = redis.from_url(settings.redis_url)
        r.publish(f"ws:{notification.user_id}", json.dumps(message))
        r.close()

        notification.status = NotificationStatus.delivered
        notification.delivered_at = datetime.utcnow()
        db.commit()
        logger.info(f"WS published: {notification_id}")

    except Exception as e:
        notification = db.get(Notification, notification_id)
        if notification:
            notification.retry_count += 1
            notification.error_message = str(e)
            if notification.retry_count >= 3:
                notification.status = NotificationStatus.dead_lettered
                notification.failed_at = datetime.utcnow()
            else:
                notification.status = NotificationStatus.failed
            db.commit()
        raise
    finally:
        db.close()