import asyncio
import hashlib
import logging
from datetime import datetime

from app.workers.celery_app import celery_app
from app.database import SyncSessionLocal

logger = logging.getLogger(__name__)


def _hash_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


async def _fetch_news_for_ticker(ticker: str, company_name: str) -> list[dict]:
    """Fetch articles from all async clients for a single ticker."""
    from app.clients import GoogleNewsClient, YahooFinanceClient

    articles: list[dict] = []

    async with GoogleNewsClient() as gn:
        try:
            results = await gn.fetch_news(f"{company_name} {ticker}", max_results=8)
            articles.extend(results)
        except Exception as exc:
            logger.warning("GoogleNews failed for %s: %s", ticker, exc)

    async with YahooFinanceClient() as yf:
        try:
            results = await yf.fetch_news(ticker, max_results=8)
            articles.extend(results)
        except Exception as exc:
            logger.warning("YahooFinance failed for %s: %s", ticker, exc)

    seen: set[str] = set()
    unique: list[dict] = []
    for a in articles:
        url = a.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(a)
    return unique


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def collect_news_task(self):
    """Collect news articles for every tracked company, then trigger sentiment."""
    from app.models import Company, NewsArticle, ArticleCompany

    logger.info("Starting news collection task")
    session = SyncSessionLocal()
    try:
        companies = session.query(Company).all()
        total_new = 0
        new_article_ids = []

        for company in companies:
            try:
                raw_articles = asyncio.run(
                    _fetch_news_for_ticker(company.ticker_symbol, company.company_name)
                )
                company_new = 0
                import re
                for a in raw_articles:
                    url = a.get("url", "")
                    if not url:
                        continue
                    aid = _hash_url(url)
                    existing = (
                        session.query(NewsArticle)
                        .filter_by(article_id=aid)
                        .first()
                    )
                    if existing:
                        continue

                    pub_date = a.get("publication_date")
                    if isinstance(pub_date, str):
                        try:
                            pub_date = datetime.fromisoformat(pub_date)
                        except (ValueError, TypeError):
                            pub_date = datetime.utcnow()
                    elif pub_date is None:
                        pub_date = datetime.utcnow()

                    title = (a.get("title") or "").strip()
                    content = (a.get("content") or a.get("description") or "").strip()
                    content = re.sub(r"<[^>]+>", "", content).strip()
                    title = re.sub(r"<[^>]+>", "", title).strip()

                    if not title:
                        continue

                    # Wrap each article in a SAVEPOINT so a single bad row doesn't
                    # nuke the entire batch; only this nested transaction rolls back.
                    try:
                        with session.begin_nested():
                            news = NewsArticle(
                                article_id=aid,
                                title=title[:2000],
                                content=content[:10000],
                                source=(a.get("source") or "unknown")[:100],
                                url=url,
                                publication_date=pub_date,
                                language="en",
                            )
                            session.add(news)
                            session.flush()

                            link = ArticleCompany(
                                article_id=aid,
                                company_id=company.company_id,
                            )
                            session.add(link)
                        new_article_ids.append(aid)
                        total_new += 1
                        company_new += 1
                    except Exception as article_exc:
                        logger.warning("Skipping article %s: %s", aid, article_exc)

                logger.info("Collected %d new articles for %s", company_new, company.ticker_symbol)
            except Exception as exc:
                session.rollback()
                logger.error("Failed collecting for %s: %s", company.ticker_symbol, exc)

        session.commit()
        logger.info("News collection complete: %d new articles total", total_new)

        if new_article_ids:
            analyze_sentiment_task.delay(new_article_ids)
            logger.info("Triggered sentiment analysis for %d articles", len(new_article_ids))

        return {"articles_collected": total_new}
    except Exception as exc:
        session.rollback()
        logger.exception("News collection task failed")
        raise self.retry(exc=exc)
    finally:
        session.close()


def _resolve_active_model_name(session) -> str | None:
    """Return the path of the active fine-tuned model, or None to use the base model."""
    from app.models import FinetuningJob

    active = (
        session.query(FinetuningJob)
        .filter(FinetuningJob.is_active == 1)
        .filter(FinetuningJob.status == "completed")
        .filter(FinetuningJob.model_path.isnot(None))
        .order_by(FinetuningJob.completed_at.desc())
        .first()
    )
    if active and active.model_path:
        return active.model_path
    return None


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def analyze_sentiment_task(self, article_ids: list):
    """Run FinBERT sentiment analysis on the given articles."""
    from app.services.sentiment_analyzer import SentimentAnalyzer
    from app.models import NewsArticle, SentimentResult

    logger.info("Analyzing sentiment for %d articles", len(article_ids))
    session = SyncSessionLocal()
    try:
        active_model = _resolve_active_model_name(session)
        if active_model:
            logger.info("Using active fine-tuned model at %s", active_model)
        analyzer = SentimentAnalyzer(model_name=active_model)

        # Skip articles that already have a sentiment result (idempotent re-runs).
        existing_ids = {
            row[0]
            for row in session.query(SentimentResult.article_id)
            .filter(SentimentResult.article_id.in_(article_ids))
            .all()
        }
        pending_ids = [a for a in article_ids if a not in existing_ids]
        if existing_ids:
            logger.info(
                "Skipping %d article(s) that already have sentiment results",
                len(existing_ids),
            )

        articles = (
            session.query(NewsArticle)
            .filter(NewsArticle.article_id.in_(pending_ids))
            .all()
        )
        results = []
        for article in articles:
            try:
                text = f"{article.title}. {article.content}" if article.content else article.title
                prediction = analyzer.analyze(text)
                with session.begin_nested():
                    result = SentimentResult(
                        article_id=article.article_id,
                        sentiment_label=prediction["sentiment_label"],
                        positive_score=prediction["positive_score"],
                        negative_score=prediction["negative_score"],
                        neutral_score=prediction["neutral_score"],
                        confidence=prediction["confidence"],
                    )
                    session.add(result)
                results.append(article.article_id)
            except Exception as exc:
                logger.error("Sentiment analysis failed for article %s: %s", article.article_id, exc)
        session.commit()
        logger.info("Sentiment analysis complete: %d results", len(results))

        if results:
            index_vector_store_task.delay()

        return {"analyzed": len(results), "skipped_existing": len(existing_ids)}
    except Exception as exc:
        session.rollback()
        logger.exception("Sentiment analysis task failed")
        raise self.retry(exc=exc)
    finally:
        session.close()


async def _fetch_adanos_for_tickers(tickers: list[str]) -> dict[str, dict]:
    """Fetch Adanos sentiment for a list of tickers concurrently."""
    from app.clients.adanos import AdanosClient
    from app.config import get_settings

    settings = get_settings()
    if not settings.ADANOS_API_KEY:
        logger.warning("ADANOS_API_KEY not configured; skipping social sentiment")
        return {}

    results: dict[str, dict] = {}
    async with AdanosClient(api_key=settings.ADANOS_API_KEY) as client:
        for ticker in tickers:
            try:
                results[ticker] = await client.get_sentiment(ticker)
            except Exception as exc:
                logger.error("Adanos fetch failed for %s: %s", ticker, exc)
    return results


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def poll_social_sentiment_task(self):
    """Fetch social / X sentiment from Adanos for all tracked companies."""
    from app.models import Company, SocialSentiment

    logger.info("Polling social sentiment")
    session = SyncSessionLocal()
    try:
        companies = session.query(Company).all()
        tickers = [c.ticker_symbol for c in companies]
        sentiment_by_ticker = asyncio.run(_fetch_adanos_for_tickers(tickers))

        count = 0
        for ticker, data in sentiment_by_ticker.items():
            if not data:
                continue
            record = SocialSentiment(
                ticker_symbol=ticker,
                buzz_score=data.get("buzz_score"),
                bullish_ratio=data.get("bullish_ratio"),
                bearish_ratio=data.get("bearish_ratio"),
                post_volume=data.get("post_volume"),
                sentiment_trend=data.get("sentiment_trend"),
            )
            session.add(record)
            count += 1

        session.commit()
        logger.info("Social sentiment poll complete: %d records", count)
        return {"records_added": count}
    except Exception as exc:
        session.rollback()
        logger.exception("Social sentiment task failed")
        raise self.retry(exc=exc)
    finally:
        session.close()


async def _run_correlations_for_tickers(tickers: list[str]) -> int:
    """Run CorrelationCalculator.compute_all_correlations for each ticker using an async session."""
    from app.database import AsyncSessionLocal
    from app.services.correlation import CorrelationCalculator

    calculator = CorrelationCalculator()
    count = 0
    async with AsyncSessionLocal() as db:
        for ticker in tickers:
            try:
                await calculator.compute_all_correlations(ticker, db)
                count += 1
            except Exception as exc:
                logger.error("Correlation update failed for %s: %s", ticker, exc)
                await db.rollback()
        await db.commit()
    return count


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def update_correlations_task(self):
    """Recalculate sentiment-price correlations for every ticker."""
    from app.models import Company

    logger.info("Updating correlations")
    session = SyncSessionLocal()
    try:
        tickers = [c.ticker_symbol for c in session.query(Company).all()]
    finally:
        session.close()

    try:
        count = asyncio.run(_run_correlations_for_tickers(tickers))
        logger.info("Correlation update complete for %d tickers", count)
        return {"tickers_updated": count}
    except Exception as exc:
        logger.exception("Correlation update task failed")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def index_vector_store_task(self):
    """Index new articles and social sentiment into ChromaDB."""
    from app.services.vector_store import VectorStoreService
    from app.models import NewsArticle, SocialSentiment

    logger.info("Indexing vector store")
    session = SyncSessionLocal()
    try:
        vs = VectorStoreService()

        recent_articles = (
            session.query(NewsArticle)
            .order_by(NewsArticle.collected_date.desc())
            .limit(200)
            .all()
        )
        article_dicts = [
            {
                "id": a.article_id,
                "title": a.title,
                "content": a.content,
                "source": a.source,
                "url": a.url,
                "publication_date": str(a.publication_date) if a.publication_date else "",
            }
            for a in recent_articles
        ]
        vs.index_articles(article_dicts)

        recent_social = (
            session.query(SocialSentiment)
            .order_by(SocialSentiment.fetched_at.desc())
            .limit(100)
            .all()
        )
        social_dicts = [
            {
                "id": str(s.id),
                "ticker_symbol": s.ticker_symbol,
                "buzz_score": float(s.buzz_score) if s.buzz_score else 0,
                "bullish_ratio": float(s.bullish_ratio) if s.bullish_ratio else 0,
                "bearish_ratio": float(s.bearish_ratio) if s.bearish_ratio else 0,
                "post_volume": s.post_volume or 0,
                "sentiment_trend": s.sentiment_trend or "",
            }
            for s in recent_social
        ]
        vs.index_social_sentiment(social_dicts)

        logger.info(
            "Vector store indexed: %d articles, %d social records",
            len(article_dicts),
            len(social_dicts),
        )
        return {"articles_indexed": len(article_dicts), "social_indexed": len(social_dicts)}
    except Exception as exc:
        logger.exception("Vector store indexing failed")
        raise self.retry(exc=exc)
    finally:
        session.close()


@celery_app.task(bind=True, max_retries=1, default_retry_delay=600)
def run_finetuning_task(self, job_id: int):
    """Execute a fine-tuning job."""
    from app.services.finetuning import FineTuningPipeline
    from app.models import FinetuningJob

    logger.info("Starting fine-tuning job %d", job_id)
    session = SyncSessionLocal()
    try:
        job = session.query(FinetuningJob).filter_by(id=job_id).first()
        if not job:
            logger.error("Fine-tuning job %d not found", job_id)
            return {"error": "Job not found"}

        job.status = "running"
        job.started_at = datetime.utcnow()
        session.commit()

        pipeline = FineTuningPipeline(session)
        pipeline.train(
            job_id=job_id,
            dataset_name=job.dataset_name,
            hyperparams=job.hyperparams or {},
        )

        session.refresh(job)
        logger.info("Fine-tuning job %d completed: %s", job_id, job.status)
        return {"job_id": job_id, "status": job.status}
    except Exception as exc:
        session.rollback()
        job = session.query(FinetuningJob).filter_by(id=job_id).first()
        if job:
            job.status = "failed"
            job.metrics = {**(job.metrics or {}), "error": str(exc)}
            session.commit()
        logger.exception("Fine-tuning job %d failed", job_id)
        raise self.retry(exc=exc)
    finally:
        session.close()
