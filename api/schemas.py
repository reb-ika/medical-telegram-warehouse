"""
api/schemas.py

Pydantic models define the shape of API responses.
FastAPI uses these to validate and serialize data automatically.
Think of them as "contracts" — the API guarantees these fields
will always be present in responses.
"""

from typing import Optional
from pydantic import BaseModel


class TopProduct(BaseModel):
    """Response for GET /api/reports/top-products"""
    term: str
    mention_count: int


class ChannelActivity(BaseModel):
    """Response for GET /api/channels/{channel_name}/activity"""
    channel_name: str
    channel_type: str
    total_posts: int
    avg_views: float
    first_post_date: str
    last_post_date: str
    posts_with_images: int


class MessageResult(BaseModel):
    """Response for GET /api/search/messages"""
    message_id: int
    channel_name: str
    message_date: str
    message_text: str
    views: int
    forwards: int
    has_image: bool


class VisualContentStat(BaseModel):
    """Response for GET /api/reports/visual-content"""
    channel_name: str
    total_messages: int
    messages_with_images: int
    image_percentage: float
    top_image_category: str