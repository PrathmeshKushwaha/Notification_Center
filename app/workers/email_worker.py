import logging
from datetime import datetime
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.workers.email_worker.deliver_email",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    queue="email_queue",
)
def deliver_email(self, notification_id: str):
    from sqlalchemy import select
    from app.core.database import get_sync_db
    from app.models.notification import Notification, NotificationStatus
    from app.models.template import Template
    from jinja2 import Template as JinjaTemplate
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from app.core.config import settings

    db = get_sync_db()
    try:
        notification = db.get(Notification, notification_id)
        if not notification:
            logger.error(f"Notification {notification_id} not found")
            return

        if notification.status == NotificationStatus.delivered:
            logger.info(f"Already delivered: {notification_id}")
            return

        notification.status = NotificationStatus.in_flight
        db.commit()

        subject = "Notification"
        body = "<p>You have a new notification.</p>"

        if notification.template_id:
            tmpl = db.get(Template, notification.template_id)
            if tmpl:
                variables = notification.variables or {}
                body = JinjaTemplate(tmpl.body).render(**variables)
                subject = JinjaTemplate(
                    tmpl.subject or "Notification"
                ).render(**variables)

        to_email = f"{notification.user_id}@example.com"

        # Send via SMTP sync
        message = MIMEMultipart("alternative")
        message["From"] = settings.smtp_from
        message["To"] = to_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.login(settings.smtp_user, settings.smtp_pass)
            server.sendmail(settings.smtp_from, to_email, message.as_string())

        notification.status = NotificationStatus.delivered
        notification.delivered_at = datetime.utcnow()
        db.commit()
        logger.info(f"Email delivered: {notification_id}")

    except Exception as e:
        notification = db.get(Notification, notification_id)
        if notification:
            notification.retry_count += 1
            notification.error_message = str(e)
            if notification.retry_count >= 3:
                notification.status = NotificationStatus.dead_lettered
                notification.failed_at = datetime.utcnow()
                logger.error(f"Dead lettered: {notification_id}")
            else:
                notification.status = NotificationStatus.failed
                logger.warning(f"Will retry: {notification_id} — {e}")
            db.commit()
        raise
    finally:
        db.close()


@celery_app.task(name="app.workers.email_worker.send_digest")
def send_digest():
    from app.core.database import get_sync_db
    from app.models.notification import Notification, NotificationStatus
    from collections import defaultdict

    db = get_sync_db()
    try:
        notifications = db.query(Notification).filter(
            Notification.status == NotificationStatus.pending,
            Notification.channel == "email",
        ).all()

        grouped = defaultdict(list)
        for n in notifications:
            grouped[n.user_id].append(n)

        for user_id, notifs in grouped.items():
            logger.info(f"Digest: {len(notifs)} pending for {user_id}")
    finally:
        db.close()