from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date


# --- Company ---
class CompanyBase(BaseModel):
    company_name: str = Field(serialization_alias="name")
    ticker_symbol: str = Field(serialization_alias="ticker")
    sector: Optional[str] = None
    industry: Optional[str] = None

class CompanyOut(CompanyBase):
    company_id: int = Field(serialization_alias="id")
    model_config = {"from_attributes": True, "populate_by_name": True}


# --- News Article ---
class NewsArticleOut(BaseModel):
    article_id: str
    title: str
    content: str
    source: str
    url: Optional[str] = None
    publication_date: datetime
    collected_date: Optional[datetime] = None
    sentiment: Optional["SentimentResultOut"] = None
    model_config = {"from_attributes": True}


# --- Sentiment Result ---
class SentimentResultOut(BaseModel):
    result_id: int
    article_id: str
    sentiment_label: str
    positive_score: float
    negative_score: float
    neutral_score: float
    confidence: float
    analyzed_date: Optional[datetime] = None
    model_config = {"from_attributes": True}

class CompanySentimentOut(BaseModel):
    company: CompanyOut
    overall_sentiment: str  # "positive" | "negative" | "neutral"
    overall_score: float = 0.0  # net score: average_positive - average_negative, in [-1, 1]
    average_positive: float
    average_negative: float
    average_neutral: float
    article_count: int
    trending: str = "stable"  # "up" | "down" | "stable" — compared to prior 7d window
    recent_articles: list[NewsArticleOut] = []
    social: Optional["SocialSentimentOut"] = None


# --- Market Data ---
class MarketDataOut(BaseModel):
    data_id: int
    ticker_symbol: str
    date: date
    open_price: Optional[float] = None
    close_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    volume: Optional[int] = None
    model_config = {"from_attributes": True}


# --- Correlation ---
class CorrelationOut(BaseModel):
    correlation_id: int
    ticker_symbol: str
    correlation_type: str
    correlation_value: float
    p_value: Optional[float] = None
    sample_size: Optional[int] = None
    time_lag: Optional[int] = None
    calculated_date: Optional[datetime] = None
    model_config = {"from_attributes": True}


# --- Trend ---
class TrendOut(BaseModel):
    trend_id: int
    ticker_symbol: str
    start_date: date
    end_date: date
    trend_direction: Optional[str] = None
    trend_strength: Optional[float] = None
    calculated_date: Optional[datetime] = None
    model_config = {"from_attributes": True}


# --- Social Sentiment ---
class SocialSentimentOut(BaseModel):
    id: int
    ticker_symbol: str
    buzz_score: Optional[float] = None
    bullish_ratio: Optional[float] = None
    bearish_ratio: Optional[float] = None
    post_volume: Optional[int] = None
    sentiment_trend: Optional[str] = None
    fetched_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# --- Chat ---
class ChatMessageCreate(BaseModel):
    content: str

class ChatMessageOut(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    citations: list = []
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

class ChatSessionCreate(BaseModel):
    title: Optional[str] = "New Chat"

class ChatSessionOut(BaseModel):
    id: int
    title: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    messages: list[ChatMessageOut] = []
    model_config = {"from_attributes": True}

class ChatSessionListOut(BaseModel):
    id: int
    title: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    message_count: int = 0
    model_config = {"from_attributes": True}


# --- Fine-tuning ---
class FinetuningJobCreate(BaseModel):
    dataset_name: str
    hyperparams: dict = Field(default_factory=lambda: {
        "learning_rate": 2e-5,
        "batch_size": 8,
        "epochs": 3,
        "warmup_steps": 100,
        "weight_decay": 0.01,
    })

class FinetuningJobOut(BaseModel):
    id: int
    dataset_name: str
    hyperparams: dict
    status: str
    metrics: dict = {}
    model_path: Optional[str] = None
    is_active: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

class DatasetInfo(BaseModel):
    name: str
    description: str
    sample_count: int
    labels: list[str]

class ModelInfo(BaseModel):
    id: str
    name: str
    is_active: bool
    accuracy: Optional[float] = None
    source: str  # "base" or "finetuned"
