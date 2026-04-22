from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base


class Company(Base):
    __tablename__ = "companies"

    company_id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(255), nullable=False, unique=True)
    ticker_symbol = Column(String(10), nullable=False, unique=True, index=True)
    sector = Column(String(100))
    industry = Column(String(100))

    articles = relationship("ArticleCompany", back_populates="company")
