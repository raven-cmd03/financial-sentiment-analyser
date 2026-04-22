from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Correlation
from app.schemas.schemas import CorrelationOut

router = APIRouter()


@router.get("/{ticker}", response_model=list[CorrelationOut])
async def get_correlations(ticker: str, db: AsyncSession = Depends(get_db)):
    ticker = ticker.upper()
    result = await db.execute(
        select(Correlation)
        .where(Correlation.ticker_symbol == ticker)
        .order_by(desc(Correlation.calculated_date))
    )
    correlations = result.scalars().all()
    return correlations
