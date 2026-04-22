"""Pydantic schema round-trip tests.

Ensures the frontend contract in `types/index.ts` doesn't drift from
`schemas.py`. The original review caught `CompanySentimentOut` missing both
`overall_score` and `trending`; this test keeps those honest.
"""

from datetime import datetime

from app.schemas.schemas import (
    ChatMessageOut,
    CompanyOut,
    CompanySentimentOut,
    NewsArticleOut,
    SentimentResultOut,
)


def _company_dict():
    return {
        "company_id": 1,
        "company_name": "Apple",
        "ticker_symbol": "AAPL",
        "sector": "Technology",
        "industry": "Consumer Electronics",
    }


def test_company_out_alias_round_trip():
    co = CompanyOut.model_validate(_company_dict())
    dumped = co.model_dump(by_alias=True)
    assert dumped["id"] == 1
    assert dumped["name"] == "Apple"
    assert dumped["ticker"] == "AAPL"


def test_company_sentiment_out_has_score_and_trending():
    payload = {
        "company": _company_dict(),
        "overall_sentiment": "positive",
        "overall_score": 0.42,
        "average_positive": 0.6,
        "average_negative": 0.18,
        "average_neutral": 0.22,
        "article_count": 5,
        "trending": "up",
        "recent_articles": [],
        "social": None,
    }
    out = CompanySentimentOut.model_validate(payload)
    dumped = out.model_dump(by_alias=True)

    # The two fields the frontend depends on MUST be present.
    assert dumped["overall_score"] == 0.42
    assert dumped["trending"] == "up"
    # Sanity: nested company still uses aliases.
    assert dumped["company"]["ticker"] == "AAPL"


def test_news_article_out_with_sentiment():
    sentiment = SentimentResultOut(
        result_id=1,
        article_id="a-1",
        sentiment_label="positive",
        positive_score=0.7,
        negative_score=0.1,
        neutral_score=0.2,
        confidence=0.7,
    )
    article = NewsArticleOut(
        article_id="a-1",
        title="t",
        content="c",
        source="s",
        publication_date=datetime.utcnow(),
        sentiment=sentiment,
    )
    dumped = article.model_dump()
    assert dumped["sentiment"]["sentiment_label"] == "positive"


def test_chat_message_out_uses_citations_not_metadata():
    msg = ChatMessageOut(
        id=1,
        session_id=1,
        role="assistant",
        content="...",
        citations=[{"article_id": "a-1", "title": "t"}],
    )
    dumped = msg.model_dump()
    # Key must be `citations`, not `metadata` — the frontend reads `m.citations`.
    assert "citations" in dumped
    assert dumped["citations"][0]["article_id"] == "a-1"
    assert "metadata" not in dumped
