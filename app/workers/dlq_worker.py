import logging
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.dlq_worker.monitor_dlq")
def monitor_dlq():
    from app.core.database import get_sync_db
    from app.models.notification import Notification, NotificationStatus

    db = get_sync_db()
    try:
        count = db.query(Notification).filter(
            Notification.status == NotificationStatus.dead_lettered
        ).count()
        if count:
            logger.warning(f"DLQ: {count} dead-lettered notifications")
        else:
            logger.info("DLQ is clean")
    finally:
        db.close()