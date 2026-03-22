from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "pulsenotify",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.email_worker",
        "app.workers.websocket_worker",
        "app.workers.webhook_worker",
        "app.workers.dlq_worker",
    ]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.workers.email_worker.deliver_email": {"queue": "email_queue"},
        "app.workers.websocket_worker.deliver_websocket": {"queue": "websocket_queue"},
        "app.workers.webhook_worker.deliver_webhook": {"queue": "webhook_queue"},
        "app.workers.dlq_worker.monitor_dlq": {"queue": "dlq_queue"},
    },
    task_queue_max_priority=10,
    task_default_priority=5,
    beat_schedule={
        "monitor-dlq-every-5-minutes": {
            "task": "app.workers.dlq_worker.monitor_dlq",
            "schedule": 300.0,
        },
        "digest-every-hour": {
            "task": "app.workers.email_worker.send_digest",
            "schedule": 3600.0,
        },
    }
)