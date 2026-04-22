from sqlalchemy import Column, Integer, String, Numeric, BigInteger, Date, UniqueConstraint
from app.database import Base


class MarketData(Base):
    __tablename__ = "market_data"

    data_id = Column(Integer, primary_key=True, autoincrement=True)
    ticker_symbol = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False)
    open_price = Column(Numeric(10, 2))
    close_price = Column(Numeric(10, 2))
    high_price = Column(Numeric(10, 2))
    low_price = Column(Numeric(10, 2))
    volume = Column(BigInteger)

    __table_args__ = (
        UniqueConstraint("ticker_symbol", "date", name="uq_ticker_date"),
    )
