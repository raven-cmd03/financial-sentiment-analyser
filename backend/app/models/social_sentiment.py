from sqlalchemy import Column, Integer, String, Numeric, DateTime, func
from app.database import Base


class SocialSentiment(Base):
    __tablename__ = "social_sentiment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker_symbol = Column(String(10), nullable=False, index=True)
    buzz_score = Column(Numeric(6, 2))
    bullish_ratio = Column(Numeric(5, 4))
    bearish_ratio = Column(Numeric(5, 4))
    post_volume = Column(Integer)
    sentiment_trend = Column(String(20))
    fetched_at = Column(DateTime, server_default=func.now(), index=True)
