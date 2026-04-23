"""Re-probe after recency-phrase patch."""
from datetime import datetime, timezone
from app.services.rag_chat import _parse_time_hints, _extract_ticker_hint
from app.services.vector_store import VectorStoreService

vs = VectorStoreService()
now = datetime.now(timezone.utc)

for q in [
    "What's the current sentiment on AAPL?",
    "Latest news on NVDA",
    "How is Tesla doing right now?",
    "Recent developments for MSFT",
    "AAPL news",
]:
    since, until = _parse_time_hints(q, now)
    ticker = _extract_ticker_hint(
        q, {"AAPL", "MSFT", "NVDA", "TSLA"}
    )
    print(f"Q: {q!r}")
    print(f"   since={since}  ticker={ticker}")
    hits = vs.search(q, n_results=3, ticker=ticker, since=since, until=until)
    for h in hits:
        m = h["metadata"]
        print(
            "   {:>19}  {}  {}".format(
                m.get("publication_date", "?"),
                m.get("source", "")[:25],
                (m.get("title", "") or "")[:70],
            )
        )
    print()
