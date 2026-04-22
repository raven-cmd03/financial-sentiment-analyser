from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis

from app.config import get_settings
from app.api import companies, news, trends, correlations, social_sentiment, chat, finetuning, websocket

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    yield
    await app.state.redis.close()


app = FastAPI(
    title=settings.APP_NAME,
    description="Intelligent financial news sentiment analysis with FinBERT, Groq-powered RAG chat, and X social sentiment",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

_origins = settings.cors_origins_list
_wildcard = _origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # Credentialed requests are incompatible with a "*" origin; only enable
    # them when the operator has listed explicit origins.
    allow_credentials=not _wildcard,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)

app.include_router(companies.router, prefix="/api/companies", tags=["Companies"])
app.include_router(news.router, prefix="/api/news", tags=["News"])
app.include_router(trends.router, prefix="/api/trends", tags=["Trends"])
app.include_router(correlations.router, prefix="/api/correlations", tags=["Correlations"])
app.include_router(social_sentiment.router, prefix="/api/social", tags=["Social Sentiment"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(finetuning.router, prefix="/api/finetuning", tags=["Fine-tuning"])
app.include_router(websocket.router, prefix="/api", tags=["WebSocket"])


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": settings.APP_NAME}
