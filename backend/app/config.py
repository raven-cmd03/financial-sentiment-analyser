from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://finsentiment:finsentiment_pass@localhost:5432/finsentiment"
    SYNC_DATABASE_URL: str = "postgresql://finsentiment:finsentiment_pass@localhost:5432/finsentiment"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # ChromaDB
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000

    # Groq
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Adanos X Sentiment
    ADANOS_API_KEY: str = ""

    # News APIs
    GOOGLE_NEWS_API_KEY: str = ""

    # Alpha Vantage (news + market data). Free tier: 5 req/min, 500 req/day.
    # When empty, Alpha Vantage is skipped and the system falls back to
    # Google News / Yahoo Finance / yfinance only.
    ALPHA_VANTAGE_API_KEY: str = ""
    # How many articles to pull per ticker per news-collection tick.
    ALPHA_VANTAGE_NEWS_LIMIT: int = 10

    # HuggingFace Hub token — only needed for gated datasets used by the
    # ``hf_corpus_backfill`` script (e.g. Brianferrell787/financial-news-
    # multisource). Generate at https://huggingface.co/settings/tokens
    # and accept the dataset's access terms before running the backfill.
    HUGGINGFACE_API_KEY: str = ""

    # Sentiment model. Default: yiyanghkust/finbert-tone — trained on
    # 10k annotated analyst-report sentences; outperforms ProsusAI/finbert
    # on financial news in independent benchmarks. The SentimentAnalyzer
    # auto-detects the label-index mapping from ``model.config.id2label``
    # so swapping to ProsusAI/finbert, ahmedrachid/FinancialBERT-Sentiment-
    # Analysis, or a fine-tuned checkpoint requires no code changes.
    FINBERT_MODEL: str = "yiyanghkust/finbert-tone"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    MODEL_DIR: str = "/app/data/models"
    DATASET_DIR: str = "/app/data/datasets"

    # App
    # SECRET_KEY is required in production. Start-up will fail if it's empty.
    SECRET_KEY: str = Field(default="", min_length=0)
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    APP_NAME: str = "Financial Sentiment Analyzer"

    # Comma-separated list of allowed CORS origins. Example: "http://localhost:3000,https://app.example.com".
    # Use "*" (single entry) only for local development; in that case credentials are disabled.
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"

    # Auth: API key required on sensitive endpoints (finetuning, chat, websocket).
    # If unset, those endpoints return 503 so we fail loudly rather than silently open.
    API_KEY: str = ""

    # Upload limits for fine-tuning dataset endpoint.
    MAX_UPLOAD_BYTES: int = 50 * 1024 * 1024  # 50 MiB

    # Scheduling
    NEWS_COLLECTION_INTERVAL_MINUTES: int = 15
    SOCIAL_SENTIMENT_INTERVAL_MINUTES: int = 60

    model_config = {"env_file": ".env", "extra": "ignore"}

    @field_validator("SECRET_KEY")
    @classmethod
    def _validate_secret_key(cls, v: str) -> str:
        # Block the common dev placeholder so deployments can't accidentally ship with it.
        if v.strip().lower() in {"change-me", "changeme", "secret", "dev"}:
            raise ValueError(
                "SECRET_KEY is set to a placeholder. Configure a real secret in .env."
            )
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
