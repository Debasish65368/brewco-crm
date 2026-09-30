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


class SegmentConvert(BaseModel):
    name: str
    description: Optional[str] = ""


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


# =====================================================
# ANALYTICS QUERY SCHEMAS
# =====================================================
from typing import Literal, Union
from pydantic import Field, field_validator

AllowedTables = Literal['customers', 'orders', 'segments', 'campaigns', 'communications']
AllowedColumns = Literal[
    'id', 'name', 'city', 'total_orders', 'total_spent', 'last_order_date', 'churn_score', 'cluster_id',
    'customer_id', 'amount', 'created_at',
    'customer_count',
    'segment_id', 'channel', 'status',
    'campaign_id', 'sent_at', 'delivered_at', 'opened_at', 'clicked_at'
]

class ColumnSpec(BaseModel):
    table: AllowedTables
    column: AllowedColumns
    agg: Optional[Literal['COUNT', 'SUM', 'AVG', 'MIN', 'MAX']] = None

class FilterSpec(BaseModel):
    table: AllowedTables
    column: AllowedColumns
    operator: Literal['=', '!=', '>', '<', '>=', '<=', 'LIKE', 'ILIKE']
    value: Any

class OrderBySpec(BaseModel):
    table: AllowedTables
    column: AllowedColumns
    agg: Optional[Literal['COUNT', 'SUM', 'AVG', 'MIN', 'MAX']] = None
    direction: Literal['ASC', 'DESC'] = 'ASC'

class QuerySpec(BaseModel):
    tables: List[AllowedTables] = Field(min_length=1)
    select: List[ColumnSpec] = Field(min_length=1)
    where: Optional[List[FilterSpec]] = []
    group_by: Optional[List[ColumnSpec]] = []
    order_by: Optional[List[OrderBySpec]] = []
    limit: int = Field(default=100, le=100)

# =====================================================
# ANALYTICS QUERY SCHEMAS
# =====================================================
from typing import Literal, Union, Any
from pydantic import Field, model_validator

AllowedTables = Literal['customers', 'orders', 'segments', 'campaigns', 'communications']
AllowedColumns = Literal[
    'id', 'name', 'city', 'total_orders', 'total_spent', 'last_order_date', 'churn_score', 'cluster_id',
    'customer_id', 'amount', 'created_at',
    'customer_count',
    'segment_id', 'channel', 'status',
    'campaign_id', 'sent_at', 'delivered_at', 'opened_at', 'clicked_at'
]

VALID_TABLE_COLUMNS = {
    'customers': {'id', 'name', 'city', 'total_orders', 'total_spent', 'last_order_date', 'churn_score', 'cluster_id', 'created_at'},
    'orders': {'id', 'customer_id', 'amount', 'created_at'},
    'segments': {'id', 'name', 'customer_count', 'created_at'},
    'campaigns': {'id', 'name', 'segment_id', 'channel', 'status', 'created_at'},
    'communications': {'campaign_id', 'customer_id', 'status', 'sent_at', 'delivered_at', 'opened_at', 'clicked_at'}
}

def validate_table_column(cls, values):
    if isinstance(values, dict) and 'table' in values and 'column' in values:
        table = values['table']
        col = values['column']
        if col not in VALID_TABLE_COLUMNS.get(table, set()):
            raise ValueError(f"Column '{col}' is not valid for table '{table}'")
    return values

class ColumnSpec(BaseModel):
    table: AllowedTables
    column: AllowedColumns
    agg: Optional[Literal['COUNT', 'SUM', 'AVG', 'MIN', 'MAX']] = None

    @model_validator(mode='before')
    @classmethod
    def check_table_col(cls, values):
        return validate_table_column(cls, values)

class FilterSpec(BaseModel):
    table: AllowedTables
    column: AllowedColumns
    operator: Literal['=', '!=', '>', '<', '>=', '<=', 'LIKE', 'ILIKE', 'IS NULL', 'IS NOT NULL']
    value: Any = None

    @model_validator(mode='before')
    @classmethod
    def check_table_col(cls, values):
        return validate_table_column(cls, values)

class OrderBySpec(BaseModel):
    table: AllowedTables
    column: AllowedColumns
    agg: Optional[Literal['COUNT', 'SUM', 'AVG', 'MIN', 'MAX']] = None
    direction: Literal['ASC', 'DESC'] = 'ASC'

    @model_validator(mode='before')
    @classmethod
    def check_table_col(cls, values):
        return validate_table_column(cls, values)

class QuerySpec(BaseModel):
    tables: List[AllowedTables] = Field(min_length=1)
    select: List[ColumnSpec] = Field(min_length=1)
    where: Optional[List[FilterSpec]] = []
    group_by: Optional[List[ColumnSpec]] = []
    order_by: Optional[List[OrderBySpec]] = []
    limit: int = Field(default=100, le=100)

from pydantic import ConfigDict
from datetime import date

class SegmentFilterSchema(BaseModel):
    model_config = ConfigDict(extra='forbid')
    
    city: Optional[str] = None
    cluster_id: Optional[int] = Field(default=None, ge=0)
    min_spent: Optional[float] = Field(default=None, ge=0)
    max_spent: Optional[float] = Field(default=None, ge=0)
    min_orders: Optional[int] = Field(default=None, ge=0)
    last_order_before: Optional[date] = None

    @model_validator(mode='after')
    def check_min_max_spent(self):
        if self.min_spent is not None and self.max_spent is not None:
            if self.min_spent > self.max_spent:
                raise ValueError('min_spent cannot be greater than max_spent')
        
        # Check if at least one filter is applied
        if all(v is None for k, v in self.model_dump().items()):
            raise ValueError('Segment must contain at least one filter condition.')
        return self
