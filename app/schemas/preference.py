from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime


class PreferenceUpdate(BaseModel):
    email_enabled: Optional[bool] = None
    websocket_enabled: Optional[bool] = None
    webhook_enabled: Optional[bool] = None
    webhook_url: Optional[str] = None
    quiet_hours_start: Optional[int] = None
    quiet_hours_end: Optional[int] = None
    timezone: Optional[str] = None


class PreferenceResponse(BaseModel):
    id: str
    user_id: str
    email_enabled: bool
    websocket_enabled: bool
    webhook_enabled: bool
    webhook_url: Optional[str]
    quiet_hours_start: Optional[int]
    quiet_hours_end: Optional[int]
    timezone: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}