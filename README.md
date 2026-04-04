# PulseNotify

A production-grade multi-channel notification platform built with Python, FastAPI, Celery, and RabbitMQ. Supports email, WebSocket, and webhook delivery with at-least-once guarantees, exponential backoff retry, dead-letter queue, and real-time observability.

---

## Architecture

Client → FastAPI (API Gateway)<br>
├── PostgreSQL (notification log, templates, preferences)<br>
├── Redis (idempotency keys, WebSocket pub/sub)<br>
└── RabbitMQ (priority queues per channel)<br>
├── Email Worker (Celery + SMTP)<br>
├── WebSocket Worker (Celery + Redis pub/sub)<br>
├── Webhook Worker (Celery + HMAC-signed HTTP POST)<br>
└── DLQ Worker (dead-letter monitor)<br>
└── Prometheus + Pushgateway + Grafana<br>

---

## Key Features

- **Multi-channel delivery** — Email (SMTP), WebSocket (realtime push), Webhook (HMAC-signed HTTP POST)
- **At-least-once delivery** — `task_acks_late=True` ensures messages survive worker crashes
- **Exponential backoff retry** — 3 attempts with configurable backoff, capped at 5 minutes
- **Dead-letter queue** — exhausted messages routed to DLQ with manual retry and discard endpoints
- **Idempotency** — duplicate requests with same key return the same notification, stored in Redis with 24hr TTL
- **Priority queuing** — critical/high/normal/low priority mapped to RabbitMQ message priorities (1-10)
- **User preferences** — per-user channel enable/disable, quiet hours, webhook URL configuration
- **Template engine** — Jinja2 templates stored in PostgreSQL, rendered at delivery time
- **Digest batching** — Celery Beat groups pending email notifications into hourly digests
- **WebSocket scaling** — Redis pub/sub routes messages across multiple FastAPI pods
- **Observability** — Prometheus metrics pushed via Pushgateway, visualized in Grafana

---

## Performance

Load tested with Locust — 50 concurrent users, 60 seconds:

| Metric | Value |
|---|---|
| Total requests | 2,280 |
| Notification throughput | 30.34 req/s |
| Median response time | 22ms |
| p95 response time | 39ms |
| p99 response time | 140ms |
| Failure rate | 0.00% |

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | Python 3.11, FastAPI, uvicorn |
| Task queue | Celery 5.4, gevent pool |
| Message broker | RabbitMQ 3.13 |
| Cache / pub-sub | Redis 7 |
| Database | PostgreSQL 16, SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Monitoring | Prometheus, Pushgateway, Grafana |
| Testing | pytest, pytest-asyncio, httpx |
| Load testing | Locust |
| Infrastructure | Docker, Docker Compose |

---

## Local Setup

### Prerequisites

- Python 3.11+
- Docker + Docker Compose
- mise (or pyenv)

### 1. Clone and install
```bash
git clone https://github.com/PrathmeshKushwaha/Notification_Center.git
cd Notification_Center
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Start infrastructure
```bash
docker compose -f infra/docker-compose.yml up -d
```

Services started:
- PostgreSQL → `localhost:5432`
- RabbitMQ → `localhost:5672` | UI → `localhost:15672`
- Redis → `localhost:6379`
- MailHog → `localhost:1025` | UI → `localhost:8025`
- Prometheus → `localhost:9090`
- Grafana → `localhost:3000`
- Pushgateway → `localhost:9091`
- Flower → `localhost:5555`

### 4. Run migrations
```bash
alembic upgrade head
```

### 5. Start the API
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Start workers
```bash
# Email worker
celery -A app.workers.celery_app worker \
  --queues=email_queue \
  --pool=gevent \
  --concurrency=10 \
  --loglevel=info

# WebSocket + Webhook + DLQ workers
celery -A app.workers.celery_app worker \
  --queues=websocket_queue,webhook_queue,dlq_queue \
  --pool=gevent \
  --concurrency=10 \
  --loglevel=info

# Celery Beat (scheduler)
celery -A app.workers.celery_app beat --loglevel=info
```

---

## API Reference

### Send notification

```json
{
  "user_id": "user-123",
  "channel": "email",
  "priority": "high",
  "template_id": "uuid",
  "variables": {"name": "Prathmesh"},
  "idempotency_key": "unique-key-001"
}
```
Returns `202 Accepted` immediately. Delivery is async.

### Check status

GET /notify/{id}/status

### Notification history

GET /notify/history?user_id=user-123&limit=20&offset=0

### Templates

POST   /templates
GET    /templates/{id}
PUT    /templates/{id}
DELETE /templates/{id}

### User preferences

GET /preferences/{user_id}
PUT /preferences/{user_id}

### Dead-letter queue

GET    /dlq
POST   /dlq/{id}/retry
DELETE /dlq/{id}

### WebSocket

WS /ws/{user_id}

### Observability

GET /health
GET /metrics

---

## Notification lifecycle

pending → queued → in_flight → delivered
→ failed (retried)
→ dead_lettered (DLQ)

---

## Running tests
```bash
pytest tests/ -v
tests/test_notifications.py::test_health_check PASSED
tests/test_notifications.py::test_create_template PASSED
tests/test_notifications.py::test_send_notification_queued PASSED
tests/test_notifications.py::test_idempotency PASSED
tests/test_notifications.py::test_notification_status PASSED
tests/test_notifications.py::test_set_preferences PASSED
tests/test_notifications.py::test_disabled_channel_rejected PASSED
tests/test_notifications.py::test_dlq_empty PASSED
tests/test_notifications.py::test_notification_history PASSED
```
9 passed in 1.01s

## Running load test
```bash
locust -f locustfile.py \
  --host=http://localhost:8000 \
  --users=50 \
  --spawn-rate=5 \
  --run-time=60s \
  --headless \
  --only-summary
```

---

## Monitoring

- **Flower** (Celery tasks) → `http://localhost:5555`
- **RabbitMQ UI** (queue depths) → `http://localhost:15672`
- **MailHog** (caught emails) → `http://localhost:8025`
- **Grafana** (delivery metrics) → `http://localhost:3000`
- **Prometheus** (raw metrics) → `http://localhost:9090`
