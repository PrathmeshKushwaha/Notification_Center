import logging
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.workers.celery_app import celery_app
from app.core.metrics import push_metric, push_retry_metric, push_dlq_metric

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
    from app.core.database import get_sync_db
    from app.models.notification import Notification, NotificationStatus
    from app.models.template import Template
    from app.core.config import settings
    from jinja2 import Template as JinjaTemplate

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

        #to_email = f"{notification.user_id}@example.com"
        to_email = "pratmshkush@gmail.com"

        message = MIMEMultipart("alternative")
        message["From"] = settings.smtp_from
        message["To"] = to_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "html"))

        start_time = time.time()

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.smtp_user, settings.smtp_pass)
            server.sendmail(settings.smtp_from, to_email, message.as_string())

        duration = time.time() - start_time

        push_metric(
            job="pulsenotify_email",
            channel="email",
            status="delivered",
            duration=duration
        )

        notification.status = NotificationStatus.delivered
        notification.delivered_at = datetime.utcnow()
        db.commit()
        logger.info(f"Email delivered: {notification_id} in {duration:.2f}s")

    except Exception as e:
        logger.error(f"Email delivery failed: {notification_id} — {e}")
        push_metric(job="pulsenotify_email", channel="email", status="failed")
        if notification:
            notification.retry_count += 1
            notification.error_message = str(e)
            if notification.retry_count >= 3:
                push_dlq_metric(channel="email")
                notification.status = NotificationStatus.dead_lettered
                notification.failed_at = datetime.utcnow()
                logger.error(f"Dead lettered: {notification_id}")
            else:
                push_retry_metric(channel="email")
                notification.status = NotificationStatus.failed
                logger.warning(f"Will retry: {notification_id}")
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