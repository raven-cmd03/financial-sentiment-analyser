import logging
from typing import Optional

import chromadb
from sentence_transformers import SentenceTransformer

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


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
        if not articles:
            return

        ids = [a["id"] for a in articles]
        documents = [
            f"{a.get('title', '')} — {a.get('content', '')[:1000]}" for a in articles
        ]
        metadatas = [
            {
                "source": a.get("source", ""),
                "url": a.get("url", ""),
                "publication_date": a.get("publication_date", ""),
                "type": "article",
            }
            for a in articles
        ]
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

    def search(self, query: str, n_results: int = 5) -> list[dict]:
        embedding = self._embed([query])
        results = self._collection.query(
            query_embeddings=embedding,
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

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
