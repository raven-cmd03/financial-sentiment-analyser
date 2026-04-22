"""Initial schema with all 11 tables

Revision ID: 001
Revises: None
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_COMPANIES = [
    ("Apple Inc.", "AAPL", "Technology", "Consumer Electronics"),
    ("Microsoft Corporation", "MSFT", "Technology", "Software"),
    ("Alphabet Inc.", "GOOGL", "Technology", "Internet Services"),
    ("Amazon.com Inc.", "AMZN", "Consumer Cyclical", "E-Commerce"),
    ("NVIDIA Corporation", "NVDA", "Technology", "Semiconductors"),
    ("Meta Platforms Inc.", "META", "Technology", "Social Media"),
    ("Tesla Inc.", "TSLA", "Consumer Cyclical", "Auto Manufacturers"),
    ("JPMorgan Chase & Co.", "JPM", "Financial Services", "Banks"),
    ("Johnson & Johnson", "JNJ", "Healthcare", "Pharmaceuticals"),
    ("Visa Inc.", "V", "Financial Services", "Credit Services"),
    ("Walmart Inc.", "WMT", "Consumer Defensive", "Discount Stores"),
    ("Procter & Gamble Co.", "PG", "Consumer Defensive", "Household Products"),
    ("UnitedHealth Group", "UNH", "Healthcare", "Health Care Plans"),
    ("Mastercard Inc.", "MA", "Financial Services", "Credit Services"),
    ("Bank of America Corp.", "BAC", "Financial Services", "Banks"),
    ("Netflix Inc.", "NFLX", "Communication Services", "Entertainment"),
    ("Adobe Inc.", "ADBE", "Technology", "Software"),
    ("Salesforce Inc.", "CRM", "Technology", "Software"),
    ("Intel Corporation", "INTC", "Technology", "Semiconductors"),
    ("Coca-Cola Company", "KO", "Consumer Defensive", "Beverages"),
]


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("company_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False, unique=True),
        sa.Column("ticker_symbol", sa.String(10), nullable=False, unique=True),
        sa.Column("sector", sa.String(100)),
        sa.Column("industry", sa.String(100)),
        sa.PrimaryKeyConstraint("company_id"),
    )
    op.create_index("ix_companies_ticker_symbol", "companies", ["ticker_symbol"])

    op.create_table(
        "news_articles",
        sa.Column("article_id", sa.String(255), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("url", sa.String(500), unique=True),
        sa.Column("publication_date", sa.DateTime(), nullable=False),
        sa.Column("collected_date", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("language", sa.String(10), server_default="en"),
        sa.PrimaryKeyConstraint("article_id"),
    )
    op.create_index("ix_news_articles_publication_date", "news_articles", ["publication_date"])
    op.create_index("ix_news_articles_source", "news_articles", ["source"])

    op.create_table(
        "article_companies",
        sa.Column("article_id", sa.String(255), sa.ForeignKey("news_articles.article_id"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.company_id"), nullable=False),
        sa.PrimaryKeyConstraint("article_id", "company_id"),
    )
    op.create_index("ix_article_companies_company_id", "article_companies", ["company_id"])

    op.create_table(
        "sentiment_results",
        sa.Column("result_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("article_id", sa.String(255), sa.ForeignKey("news_articles.article_id")),
        sa.Column("sentiment_label", sa.String(20), nullable=False),
        sa.Column("positive_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("negative_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("neutral_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("analyzed_date", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("result_id"),
    )
    op.create_index("ix_sentiment_results_article_id", "sentiment_results", ["article_id"])
    op.create_index("ix_sentiment_results_sentiment_label", "sentiment_results", ["sentiment_label"])
    op.create_index("ix_sentiment_results_analyzed_date", "sentiment_results", ["analyzed_date"])

    op.create_table(
        "market_data",
        sa.Column("data_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker_symbol", sa.String(10), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open_price", sa.Numeric(10, 2)),
        sa.Column("close_price", sa.Numeric(10, 2)),
        sa.Column("high_price", sa.Numeric(10, 2)),
        sa.Column("low_price", sa.Numeric(10, 2)),
        sa.Column("volume", sa.BigInteger()),
        sa.PrimaryKeyConstraint("data_id"),
        sa.UniqueConstraint("ticker_symbol", "date", name="uq_ticker_date"),
    )
    op.create_index("ix_market_data_ticker_date", "market_data", ["ticker_symbol", "date"])

    op.create_table(
        "correlations",
        sa.Column("correlation_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker_symbol", sa.String(10), nullable=False),
        sa.Column("correlation_type", sa.String(50), nullable=False),
        sa.Column("correlation_value", sa.Numeric(5, 4), nullable=False),
        sa.Column("p_value", sa.Numeric(10, 8)),
        sa.Column("sample_size", sa.Integer()),
        sa.Column("time_lag", sa.Integer()),
        sa.Column("calculated_date", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("correlation_id"),
    )
    op.create_index("ix_correlations_ticker_symbol", "correlations", ["ticker_symbol"])
    op.create_index("ix_correlations_calculated_date", "correlations", ["calculated_date"])

    op.create_table(
        "trends",
        sa.Column("trend_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker_symbol", sa.String(10), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("trend_direction", sa.String(20)),
        sa.Column("trend_strength", sa.Numeric(5, 4)),
        sa.Column("calculated_date", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("trend_id"),
    )
    op.create_index("ix_trends_ticker_dates", "trends", ["ticker_symbol", "start_date", "end_date"])

    op.create_table(
        "social_sentiment",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker_symbol", sa.String(10), nullable=False),
        sa.Column("buzz_score", sa.Numeric(6, 2)),
        sa.Column("bullish_ratio", sa.Numeric(5, 4)),
        sa.Column("bearish_ratio", sa.Numeric(5, 4)),
        sa.Column("post_volume", sa.Integer()),
        sa.Column("sentiment_trend", sa.String(20)),
        sa.Column("fetched_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_social_sentiment_ticker", "social_sentiment", ["ticker_symbol"])
    op.create_index("ix_social_sentiment_fetched_at", "social_sentiment", ["fetched_at"])

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(255), server_default="New Chat"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), server_default="[]"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])

    op.create_table(
        "finetuning_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_name", sa.String(255), nullable=False),
        sa.Column("hyperparams", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("metrics", sa.JSON(), server_default="{}"),
        sa.Column("model_path", sa.String(500)),
        sa.Column("is_active", sa.Integer(), server_default="0"),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # Seed companies
    companies_table = sa.table(
        "companies",
        sa.column("company_name", sa.String),
        sa.column("ticker_symbol", sa.String),
        sa.column("sector", sa.String),
        sa.column("industry", sa.String),
    )
    op.bulk_insert(companies_table, [
        {"company_name": name, "ticker_symbol": ticker, "sector": sector, "industry": industry}
        for name, ticker, sector, industry in SEED_COMPANIES
    ])


def downgrade() -> None:
    op.drop_table("finetuning_jobs")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("social_sentiment")
    op.drop_table("trends")
    op.drop_table("correlations")
    op.drop_table("market_data")
    op.drop_table("sentiment_results")
    op.drop_table("article_companies")
    op.drop_table("news_articles")
    op.drop_table("companies")
