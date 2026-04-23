import logging
from datetime import datetime, timezone
from typing import Optional

import chromadb
from sentence_transformers import SentenceTransformer

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _to_epoch_seconds(value: datetime | str | None) -> int | None:
    """Convert a datetime or string to a UTC epoch-second integer.

    Chroma's numeric operators (``$gte``/``$lte``) reject string values — we
    learned this the hard way — so we store ``publication_date_ts`` as a
    numeric mirror of the existing human-readable ``publication_date``
    string. Both live on every indexed document.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return int(datetime.strptime(s, fmt).replace(
                tzinfo=timezone.utc
            ).timestamp())
        except ValueError:
            continue
    return None


class VectorStoreService:
    """Thin wrapper around ChromaDB for financial document retrieval."""

    COLLECTION_NAME = "financial_documents"

    def __init__(
        self,
        chroma_client: Optional[chromadb.HttpClient] = None,
        embedding_model: Optional[SentenceTransformer] = None,
    ):
        self._client = chroma_client or chromadb.HttpClient(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT,
        )
        self._embedder = embedding_model or SentenceTransformer(settings.EMBEDDING_MODEL)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return self._embedder.encode(texts, show_progress_bar=False).tolist()

    def index_articles(self, articles: list[dict]) -> None:
        """Upsert article chunks into Chroma.

        Each ``articles`` entry may carry a ``tickers`` list of symbols from
        the ``article_companies`` junction; the first symbol is stored as the
        filterable ``ticker`` scalar (Chroma metadata must be scalar) and the
        full set is preserved as a comma-joined ``tickers_all`` string so the
        LLM can still see co-mentions.
        """
        if not articles:
            return

        ids = [a["id"] for a in articles]
        documents = [
            f"{a.get('title', '')} — {a.get('content', '')[:1000]}" for a in articles
        ]
        metadatas = []
        for a in articles:
            tickers = a.get("tickers") or []
            title = a.get("title", "")
            pub_date_raw = a.get("publication_date", "")
            meta: dict = {
                "source": a.get("source", ""),
                "url": a.get("url", ""),
                "publication_date": pub_date_raw,
                "type": "article",
                "title": title,
            }
            pub_ts = _to_epoch_seconds(pub_date_raw)
            if pub_ts is not None:
                meta["publication_date_ts"] = pub_ts
            if tickers:
                meta["ticker"] = tickers[0]
                meta["tickers_all"] = ",".join(tickers)
            metadatas.append(meta)
        embeddings = self._embed(documents)

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info("Indexed %d articles into ChromaDB", len(articles))

    def index_social_sentiment(self, records: list[dict]) -> None:
        if not records:
            return

        ids = [f"social_{r['id']}" for r in records]
        documents = [
            f"Social sentiment for {r['ticker_symbol']}: "
            f"buzz={r.get('buzz_score', 0)}, bullish={r.get('bullish_ratio', 0)}, "
            f"bearish={r.get('bearish_ratio', 0)}, volume={r.get('post_volume', 0)}, "
            f"trend={r.get('sentiment_trend', '')}"
            for r in records
        ]
        metadatas = [
            {
                "ticker": r.get("ticker_symbol", ""),
                "type": "social_sentiment",
            }
            for r in records
        ]
        embeddings = self._embed(documents)

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info("Indexed %d social sentiment records into ChromaDB", len(records))

    def search(
        self,
        query: str,
        n_results: int = 5,
        *,
        since: datetime | str | None = None,
        until: datetime | str | None = None,
        ticker: str | None = None,
    ) -> list[dict]:
        """Semantic search with optional temporal + ticker scoping.

        Dates are compared against the numeric ``publication_date_ts`` field
        (epoch seconds, UTC). Chroma requires ``$gte``/``$lte`` operands to
        be numeric — the earlier string-based impl silently blew up at query
        time.

        All filter args are optional; pass nothing for an unfiltered semantic
        search.
        """
        embedding = self._embed([query])

        clauses: list[dict] = []
        since_ts = _to_epoch_seconds(since)
        until_ts = _to_epoch_seconds(until)
        if since_ts is not None:
            clauses.append({"publication_date_ts": {"$gte": since_ts}})
        if until_ts is not None:
            clauses.append({"publication_date_ts": {"$lte": until_ts}})
        if ticker:
            clauses.append({"ticker": {"$eq": ticker.upper()}})

        where: dict | None = None
        if len(clauses) == 1:
            where = clauses[0]
        elif len(clauses) > 1:
            where = {"$and": clauses}

        query_kwargs: dict = {
            "query_embeddings": embedding,
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where is not None:
            query_kwargs["where"] = where

        results = self._collection.query(**query_kwargs)

        hits: list[dict] = []
        if results and results["ids"]:
            for i, doc_id in enumerate(results["ids"][0]):
                hits.append(
                    {
                        "id": doc_id,
                        "document": results["documents"][0][i] if results["documents"] else "",
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else None,
                    }
                )
        return hits
