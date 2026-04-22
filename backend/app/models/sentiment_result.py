from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class SentimentResult(Base):
    __tablename__ = "sentiment_results"

    result_id = Column(Integer, primary_key=True, autoincrement=True)
    # One sentiment row per article. The worker additionally guards against
    # duplicates, but the unique index is the authoritative invariant.
    article_id = Column(
        String(255),
        ForeignKey("news_articles.article_id"),
        index=True,
        unique=True,
        nullable=False,
    )
    sentiment_label = Column(String(20), nullable=False, index=True)
    positive_score = Column(Numeric(5, 4), nullable=False)
    negative_score = Column(Numeric(5, 4), nullable=False)
    neutral_score = Column(Numeric(5, 4), nullable=False)
    confidence = Column(Numeric(5, 4), nullable=False)
    analyzed_date = Column(DateTime, server_default=func.now(), index=True)

    article = relationship("NewsArticle", back_populates="sentiment_results")
