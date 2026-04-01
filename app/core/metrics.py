from prometheus_client import (
    Counter, Histogram, Gauge,
    CollectorRegistry, push_to_gateway,
    generate_latest, CONTENT_TYPE_LATEST
)

notifications_sent_total = Counter(
    "notifications_sent_total",
    "Total notifications sent",
    ["channel", "status"]
)

notification_delivery_duration_seconds = Histogram(
    "notification_delivery_duration_seconds",
    "Notification delivery duration in seconds",
    ["channel"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

notifications_retry_total = Counter(
    "notifications_retry_total",
    "Total notification retries",
    ["channel"]
)

notifications_dlq_total = Counter(
    "notifications_dlq_total",
    "Total notifications dead lettered",
    ["channel"]
)

active_websocket_connections = Gauge(
    "active_websocket_connections",
    "Current active WebSocket connections"
)


def get_metrics():
    return generate_latest()


def push_metric(job: str, channel: str, status: str, duration: float = None):
    registry = CollectorRegistry()
    sent = Counter(
        "notifications_sent_total",
        "Total notifications sent",
        ["channel", "status"],
        registry=registry
    )
    sent.labels(channel=channel, status=status).inc()

    if duration is not None:
        hist = Histogram(
            "notification_delivery_duration_seconds",
            "Delivery duration",
            ["channel"],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=registry
        )
        hist.labels(channel=channel).observe(duration)

    try:
        push_to_gateway(
            "localhost:9091",
            job=job,
            registry=registry
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Pushgateway error: {e}")


def push_retry_metric(channel: str):
    registry = CollectorRegistry()
    counter = Counter(
        "notifications_retry_total",
        "Total retries",
        ["channel"],
        registry=registry
    )
    counter.labels(channel=channel).inc()
    try:
        push_to_gateway(
            "localhost:9091",
            job="pulsenotify_retry",
            registry=registry
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Pushgateway error: {e}")


def push_dlq_metric(channel: str):
    registry = CollectorRegistry()
    counter = Counter(
        "notifications_dlq_total",
        "Total DLQ",
        ["channel"],
        registry=registry
    )
    counter.labels(channel=channel).inc()
    try:
        push_to_gateway(
            "localhost:9091",
            job="pulsenotify_dlq",
            registry=registry
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Pushgateway error: {e}")
