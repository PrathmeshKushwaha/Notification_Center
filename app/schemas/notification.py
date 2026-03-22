from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.notification import NotificationChannel, NotificationPriority, NotificationStatus


class NotificationCreate(BaseModel):
    user_id: str
    channel: NotificationChannel
    priority: NotificationPriority = NotificationPriority.normal
    template_id: Optional[str] = None
    variables: Dict[str, Any] = {}
    idempotency_key: Optional[str] = None


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    channel: NotificationChannel
    priority: NotificationPriority
    status: NotificationStatus
    template_id: Optional[str]
    variables: Dict[str, Any]
    idempotency_key: Optional[str]
    retry_count: int
    error_message: Optional[str]
    created_at: datetime
    queued_at: Optional[datetime]
    delivered_at: Optional[datetime]
    failed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class NotificationStatusResponse(BaseModel):
    id: str
    status: NotificationStatus
    retry_count: int
    error_message: Optional[str]
    created_at: datetime
    delivered_at: Optional[datetime]
    failed_at: Optional[datetime]

    model_config = {"from_attributes": True}