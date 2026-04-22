from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, func
from app.database import Base


class Trend(Base):
    __tablename__ = "trends"

    trend_id = Column(Integer, primary_key=True, autoincrement=True)
    ticker_symbol = Column(String(10), nullable=False, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    trend_direction = Column(String(20))
    trend_strength = Column(Numeric(5, 4))
    calculated_date = Column(DateTime, server_default=func.now())
