"""Throwaway live smoke test for GDELT — delete after verification."""
import asyncio
from datetime import datetime, timedelta

from app.clients import GdeltClient


async def main() -> None:
    async with GdeltClient() as c:
        now = datetime.utcnow()
        query = 'AAPL OR "Apple Inc"'
        articles = await c.fetch_news(
            query,
            max_results=10,
            time_from=now - timedelta(days=14),
            time_to=now,
        )
        print(f"Retrieved {len(articles)} articles from GDELT for {query!r}")
        for a in articles[:5]:
            title = a["title"][:90]
            print(f"  - [{a['publication_date']}] {a['source']}: {title}")


if __name__ == "__main__":
    asyncio.run(main())
