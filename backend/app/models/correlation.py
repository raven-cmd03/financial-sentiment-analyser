from sqlalchemy import Column, Integer, String, Numeric, DateTime, func
from app.database import Base


class Correlation(Base):
    __tablename__ = "correlations"

    correlation_id = Column(Integer, primary_key=True, autoincrement=True)
    ticker_symbol = Column(String(10), nullable=False, index=True)
    correlation_type = Column(String(50), nullable=False)
    correlation_value = Column(Numeric(5, 4), nullable=False)
    p_value = Column(Numeric(10, 8))
    sample_size = Column(Integer)
    time_lag = Column(Integer)
    calculated_date = Column(DateTime, server_default=func.now(), index=True)
