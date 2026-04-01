import logging
import hmac
import hashlib
import json
import time
from datetime import datetime
import httpx
from app.workers.celery_app import celery_app
from app.core.metrics import push_metric, push_retry_metric, push_dlq_metric

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.workers.webhook_worker.deliver_webhook",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    queue="webhook_queue",
)
def deliver_webhook(self, notification_id: str):
    from app.core.database import get_sync_db
    from app.models.notification import Notification, NotificationStatus
    from app.models.preference import UserPreference
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

        pref = db.query(UserPreference).filter(
            UserPreference.user_id == notification.user_id
        ).first()

        if not pref or not pref.webhook_url:
            notification.status = NotificationStatus.failed
            notification.error_message = "No webhook URL configured"
            db.commit()
            logger.warning(f"No webhook URL for {notification.user_id}")
            return

        notification.status = NotificationStatus.in_flight
        db.commit()

        payload = {
            "notification_id": notification.id,
            "user_id": notification.user_id,
            "channel": notification.channel,
            "variables": notification.variables,
            "created_at": str(notification.created_at),
        }

        body = json.dumps(payload, separators=(",", ":"))
        signature = hmac.new(
            settings.secret_key.encode(),
            body.encode(),
            hashlib.sha256
        ).hexdigest()

        start_time = time.time()

        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                pref.webhook_url,
                json=payload,
                headers={"X-PulseNotify-Signature": signature}
            )
            response.raise_for_status()

        duration = time.time() - start_time

        push_metric(
            job="pulsenotify_webhook",
            channel="webhook",
            status="delivered",
            duration=duration
        )

        notification.status = NotificationStatus.delivered
        notification.delivered_at = datetime.utcnow()
        db.commit()
        logger.info(
            f"Webhook delivered: {notification_id} "
            f"to {pref.webhook_url} in {duration:.2f}s"
        )

    except Exception as e:
        logger.error(f"Webhook delivery failed: {notification_id} — {e}")
        push_metric(
            job="pulsenotify_webhook",
            channel="webhook",
            status="failed"
        )
        if notification:
            notification.retry_count += 1
            notification.error_message = str(e)
            if notification.retry_count >= 3:
                push_dlq_metric(channel="webhook")
                notification.status = NotificationStatus.dead_lettered
                notification.failed_at = datetime.utcnow()
                logger.error(f"Dead lettered: {notification_id}")
            else:
                push_retry_metric(channel="webhook")
                notification.status = NotificationStatus.failed
                logger.warning(f"Will retry: {notification_id}")
            db.commit()
        raise
    finally:
        db.close()