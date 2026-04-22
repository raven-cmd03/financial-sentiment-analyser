// Types derived from backend Pydantic schemas in backend/app/schemas/schemas.py.
// Keep this file in sync when backend schemas change.

export interface Company {
  id: number;
  ticker: string;
  name: string;
  sector?: string | null;
  industry?: string | null;
}

export interface SentimentResult {
  result_id: number;
  article_id: string;
  sentiment_label: "positive" | "negative" | "neutral" | string;
  positive_score: number;
  negative_score: number;
  neutral_score: number;
  confidence: number;
  analyzed_date?: string | null;
}

export interface NewsArticle {
  article_id: string;
  title: string;
  content: string;
  source: string;
  url?: string | null;
  publication_date: string;
  collected_date?: string | null;
  sentiment?: SentimentResult | null;
}

export interface SocialSentiment {
  id: number;
  ticker_symbol: string;
  buzz_score?: number | null;
  bullish_ratio?: number | null;
  bearish_ratio?: number | null;
  post_volume?: number | null;
  sentiment_trend?: string | null;
  fetched_at?: string | null;
}

export interface CompanySentiment {
  company: Company;
  overall_sentiment: "positive" | "negative" | "neutral" | string;
  overall_score: number; // net score in [-1, 1] (average_positive - average_negative)
  average_positive: number;
  average_negative: number;
  average_neutral: number;
  article_count: number;
  trending: "up" | "down" | "stable" | string;
  recent_articles: NewsArticle[];
  social?: SocialSentiment | null;
}

export interface MarketData {
  data_id: number;
  ticker_symbol: string;
  date: string;
  open_price?: number | null;
  close_price?: number | null;
  high_price?: number | null;
  low_price?: number | null;
  volume?: number | null;
}

export interface CorrelationData {
  correlation_id: number;
  ticker_symbol: string;
  correlation_type: string;
  correlation_value: number;
  p_value?: number | null;
  sample_size?: number | null;
  time_lag?: number | null;
  calculated_date?: string | null;
}

export interface TrendData {
  date: string;
  sentiment_score: number;
  article_count: number;
  positive_ratio: number;
  negative_ratio: number;
  neutral_ratio: number;
  ticker?: string;
}

export interface ChatSession {
  id: number | string;
  title: string;
  created_at?: string | null;
  updated_at?: string | null;
  message_count?: number;
  messages?: ChatMessage[];
}

export interface ChatMessage {
  id: number | string;
  session_id: number | string;
  role: "user" | "assistant" | string;
  content: string;
  citations?: Array<Record<string, unknown>>;
  created_at?: string | null;
}

export interface FinetuningJob {
  id: number;
  dataset_name: string;
  hyperparams: Record<string, unknown>;
  status: "pending" | "running" | "completed" | "failed" | string;
  metrics?: Record<string, unknown>;
  model_path?: string | null;
  is_active?: number;
  started_at?: string | null;
  completed_at?: string | null;
  created_at?: string | null;
}

export interface DatasetInfo {
  name: string;
  description: string;
  sample_count: number;
  labels: string[];
}

export interface ModelInfo {
  id: string;
  name: string;
  is_active: boolean;
  accuracy?: number | null;
  source: "base" | "finetuned" | string;
}
