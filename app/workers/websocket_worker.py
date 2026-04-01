import logging
import json
import redis
import time
from datetime import datetime
from app.workers.celery_app import celery_app
from app.core.metrics import push_metric, push_retry_metric, push_dlq_metric

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
    from app.core.database import get_sync_db
    from app.models.notification import Notification, NotificationStatus
    from app.core.config import settings

    db = get_sync_db()
    notification = None
    try:
        # Retry DB get to handle FastAPI commit timing race
        for attempt in range(3):
            notification = db.get(Notification, notification_id)
            if notification:
                break
            db.expire_all()
            time.sleep(0.5)

        if not notification:
            logger.error(f"Notification not found: {notification_id}")
            return

        if notification.status == NotificationStatus.delivered:
            logger.info(f"Already delivered: {notification_id}")
            return

        notification.status = NotificationStatus.in_flight
        db.commit()

        message = {
            "id": notification.id,
            "channel": notification.channel,
            "variables": notification.variables,
            "created_at": str(notification.created_at),
        }

        start_time = time.time()
        r = redis.from_url(settings.redis_url)
        receivers = r.publish(
            f"ws:{notification.user_id}",
            json.dumps(message)
        )
        r.close()
        duration = time.time() - start_time

        push_metric(
            job="pulsenotify_ws",
            channel="websocket",
            status="delivered",
            duration=duration
        )

        if receivers == 0:
            logger.warning(
                f"No active WS connection for {notification.user_id}"
            )

        notification.status = NotificationStatus.delivered
        notification.delivered_at = datetime.utcnow()
        db.commit()
        logger.info(
            f"WS delivered: {notification_id} "
            f"to {receivers} receiver(s) in {duration:.3f}s"
        )

    except Exception as e:
        logger.error(f"WS delivery failed: {notification_id} — {e}")
        push_metric(job="pulsenotify_ws", channel="websocket", status="failed")
        if notification:
            notification.retry_count += 1
            notification.error_message = str(e)
            if notification.retry_count >= 3:
                push_dlq_metric(channel="websocket")
                notification.status = NotificationStatus.dead_lettered
                notification.failed_at = datetime.utcnow()
                logger.error(f"Dead lettered: {notification_id}")
            else:
                push_retry_metric(channel="websocket")
                notification.status = NotificationStatus.failed
                logger.warning(f"Will retry: {notification_id}")
            db.commit()
        raise
    finally:
        db.close()