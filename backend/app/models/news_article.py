from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class NewsArticle(Base):
    __tablename__ = "news_articles"

    article_id = Column(String(255), primary_key=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    source = Column(String(100), nullable=False, index=True)
    url = Column(Text, unique=True)
    publication_date = Column(DateTime, nullable=False, index=True)
    collected_date = Column(DateTime, server_default=func.now())
    language = Column(String(10), default="en")

    sentiment_results = relationship("SentimentResult", back_populates="article")
    companies = relationship("ArticleCompany", back_populates="article")


class ArticleCompany(Base):
    __tablename__ = "article_companies"

    article_id = Column(String(255), ForeignKey("news_articles.article_id"), primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), primary_key=True, index=True)

    article = relationship("NewsArticle", back_populates="companies")
    company = relationship("Company", back_populates="articles")
