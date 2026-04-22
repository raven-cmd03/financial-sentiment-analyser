"""Deduplicate sentiment_results and add unique index on article_id

Revision ID: 002
Revises: 001
Create Date: 2026-04-22 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Collapse any existing duplicate rows (keep the most recent per article).
    op.execute(
        """
        DELETE FROM sentiment_results a
        USING sentiment_results b
        WHERE a.article_id = b.article_id
          AND a.result_id < b.result_id
        """
    )

    # Enforce NOT NULL on article_id going forward.
    op.alter_column(
        "sentiment_results",
        "article_id",
        existing_type=sa.String(255),
        nullable=False,
    )

    # Drop the old non-unique index and replace it with a unique one.
    op.drop_index("ix_sentiment_results_article_id", table_name="sentiment_results")
    op.create_index(
        "ix_sentiment_results_article_id",
        "sentiment_results",
        ["article_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_sentiment_results_article_id", table_name="sentiment_results")
    op.create_index(
        "ix_sentiment_results_article_id",
        "sentiment_results",
        ["article_id"],
        unique=False,
    )
    op.alter_column(
        "sentiment_results",
        "article_id",
        existing_type=sa.String(255),
        nullable=True,
    )
