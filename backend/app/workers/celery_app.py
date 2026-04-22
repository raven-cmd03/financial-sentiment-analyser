from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "financial_sentiment",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
)

celery_app.conf.beat_schedule = {
    "collect-news": {
        "task": "app.workers.tasks.collect_news_task",
        "schedule": settings.NEWS_COLLECTION_INTERVAL_MINUTES * 60,  # every 15 min
    },
    "poll-social-sentiment": {
        "task": "app.workers.tasks.poll_social_sentiment_task",
        "schedule": settings.SOCIAL_SENTIMENT_INTERVAL_MINUTES * 60,  # every 60 min
    },
    "collect-market-data": {
        "task": "app.workers.tasks.collect_market_data_task",
        # Pull fresh OHLCV shortly after US market close; correlations run
        # 30 minutes later so they always see the day's final prices.
        "schedule": crontab(hour=16, minute=30),
    },
    "update-correlations": {
        "task": "app.workers.tasks.update_correlations_task",
        "schedule": crontab(hour=17, minute=0),  # daily at 17:00 UTC (market close)
    },
    "index-vector-store": {
        "task": "app.workers.tasks.index_vector_store_task",
        "schedule": 30 * 60,  # every 30 min
    },
}

celery_app.conf.task_routes = {}

celery_app.autodiscover_tasks(["app.workers"])
