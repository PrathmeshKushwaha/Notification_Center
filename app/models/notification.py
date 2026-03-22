from app.models.base import Base

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base
import enum


class NotificationChannel(str, enum.Enum):
    email = "email"
    websocket = "websocket"
    webhook = "webhook"


class NotificationPriority(str, enum.Enum):
    critical = "critical"
    high = "high"
    normal = "normal"
    low = "low"


class NotificationStatus(str, enum.Enum):
    pending = "pending"
    queued = "queued"
    in_flight = "in_flight"
    delivered = "delivered"
    failed = "failed"
    dead_lettered = "dead_lettered"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(
        SAEnum(NotificationChannel), nullable=False
    )
    priority: Mapped[str] = mapped_column(
        SAEnum(NotificationPriority), nullable=False,
        default=NotificationPriority.normal
    )
    status: Mapped[str] = mapped_column(
        SAEnum(NotificationStatus), nullable=False,
        default=NotificationStatus.pending, index=True
    )
    template_id: Mapped[str] = mapped_column(String(255), nullable=True)
    variables: Mapped[dict] = mapped_column(JSONB, nullable=True, default={})
    idempotency_key: Mapped[str] = mapped_column(
        String(512), nullable=True, unique=True, index=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    queued_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    failed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)