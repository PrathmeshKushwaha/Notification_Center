import logging
import hmac
import hashlib
import json
from datetime import datetime
import httpx
from app.workers.celery_app import celery_app

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
    try:
        notification = db.get(Notification, notification_id)
        if not notification:
            return

        if notification.status == NotificationStatus.delivered:
            return

        pref = db.query(UserPreference).filter(
            UserPreference.user_id == notification.user_id
        ).first()

        if not pref or not pref.webhook_url:
            notification.status = NotificationStatus.failed
            notification.error_message = "No webhook URL configured"
            db.commit()
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

        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                pref.webhook_url,
                json=payload,
                headers={"X-PulseNotify-Signature": signature}
            )
            response.raise_for_status()

        notification.status = NotificationStatus.delivered
        notification.delivered_at = datetime.utcnow()
        db.commit()
        logger.info(f"Webhook delivered: {notification_id}")

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