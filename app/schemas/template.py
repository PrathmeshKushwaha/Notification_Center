from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.template import TemplateChannel


class TemplateCreate(BaseModel):
    name: str
    channel: TemplateChannel
    subject: Optional[str] = None
    body: str


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    channel: TemplateChannel
    subject: Optional[str]
    body: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}