from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, EmailStr


# =====================================================
# CUSTOMER SCHEMAS
# =====================================================

class CustomerCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str
    city: str
    total_orders: int = 0
    total_spent: float = 0
    last_order_date: Optional[datetime] = None


class CustomerBulkRequest(BaseModel):
    customers: List[CustomerCreate]


class CustomerFilterQuery(BaseModel):
    city: Optional[str] = None
    min_spent: Optional[float] = None
    max_spent: Optional[float] = None
    min_orders: Optional[int] = None


# =====================================================
# ORDER SCHEMAS
# =====================================================

class OrderCreate(BaseModel):
    customer_id: int
    amount: float
    items: List[Dict[str, Any]]
    created_at: Optional[datetime] = None


class OrderBulkRequest(BaseModel):
    orders: List[OrderCreate]


# =====================================================
# SEGMENT SCHEMAS
# =====================================================

class SegmentCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    filter_json: Dict[str, Any]


class SegmentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    filter_json: Dict[str, Any]
    customer_count: int
    created_at: datetime


# =====================================================
# CAMPAIGN SCHEMAS
# =====================================================

class CampaignCreate(BaseModel):
    name: str
    segment_id: int
    message: str
    channel: str


class CampaignResponse(BaseModel):
    id: int
    name: str
    segment_id: int
    message: str
    channel: str
    status: str
    created_at: datetime


# =====================================================
# COMMUNICATION SCHEMAS
# =====================================================

class CommunicationReceipt(BaseModel):
    campaign_id: int
    customer_id: int
    status: str


# =====================================================
# DASHBOARD SCHEMAS
# =====================================================

class DashboardStats(BaseModel):
    total_customers: int
    total_orders: int
    total_revenue: float
    total_campaigns: int
    delivered: int
    opened: int
    clicked: int


# =====================================================
# AI SCHEMAS
# =====================================================

class SegmentSuggestionRequest(BaseModel):
    prompt: str


class DraftMessageRequest(BaseModel):
    goal: str


class AISegmentResponse(BaseModel):
    filter_json: Dict[str, Any]


class AIDraftResponse(BaseModel):
    message: str
