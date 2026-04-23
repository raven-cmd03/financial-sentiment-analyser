import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

from langchain_groq import ChatGroq
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import ChatMessage, ChatSession
from app.services.vector_store import VectorStoreService


class RAGChatEvent(dict):
    """Simple typed wrapper for streamed chat events.

    Emitted events are JSON-serializable dicts with the shape::

        {"token": str}                 # for incremental text
        {"citations": list[dict]}       # emitted once before the first token
    """

logger = logging.getLogger(__name__)
settings = get_settings()


def _build_system_prompt(now_utc: datetime) -> str:
    """Render the system prompt with the current UTC date baked in.

    LLMs have no implicit knowledge of the current date — they fall back to
    their training cutoff, which for Llama 3.3 is well before 2026. Without
    this anchor, questions like "summarise yesterday's news" silently
    resolve against a year-stale calendar and citations come out dated
    2024/2025 even though our corpus is 2026-fresh.
    """
    today = now_utc.strftime("%Y-%m-%d")
    return (
        f"You are an expert financial research assistant powered by the Financial Sentiment "
        f"Analyzer platform.\n\n"
        f"Today's date is {today} (UTC). When the user says \"today\", \"yesterday\", "
        f'"this week", etc., resolve it relative to this date — do NOT fall back to your '
        f"training cutoff.\n\n"
        f"Your role is to help users understand market sentiment, news analysis, and "
        f"financial trends.\n\n"
        f"Guidelines:\n"
        f"- Provide clear, data-driven analysis grounded in the retrieved context.\n"
        f"- Every retrieved document is prefixed with its source and publication date in "
        f"the form ``[source | YYYY-MM-DD] body``. Cite the EXACT date shown — never "
        f"invent one. Example citation: ``[Source: <publication>, <YYYY-MM-DD>]``.\n"
        f"- If the retrieved context does not contain enough information to answer "
        f"confidently, say so rather than speculating.\n"
        f"- Present balanced viewpoints — mention both bullish and bearish signals when "
        f"relevant.\n"
        f"- Use financial terminology accurately but explain complex concepts when needed.\n\n"
        f"IMPORTANT DISCLAIMER: Your analysis is for informational and educational "
        f"purposes only. It does not constitute financial advice. Users should consult a "
        f"qualified financial advisor before making investment decisions."
    )


# Matches a 1-5 letter uppercase ticker token in the user's question. Used as
# a best-effort ticker-scope hint; unmatched queries fall back to pure
# semantic search.
_TICKER_RE = re.compile(r"\b([A-Z]{1,5})\b")


# Phrases that imply "give me recent news" without naming a specific window.
# We map them to a ~30-day lookback so questions like "What's the current
# sentiment on AAPL?" don't let pure semantic similarity pull up 2007 hits.
# 30 days is deliberately generous: short enough to exclude stale archival
# pieces, long enough to catch earnings cycles + weekly analyst reports.
_RECENCY_PHRASES = (
    "current",
    "currently",
    "latest",
    "most recent",
    "right now",
    "as of now",
    "at the moment",
    "today's",
    "these days",
    "nowadays",
    "recently",
)


def _parse_time_hints(
    question: str, now_utc: datetime
) -> tuple[datetime | None, datetime | None]:
    """Best-effort extraction of a ``(since, until)`` window from the user's
    question. Returns ``(None, None)`` when no temporal phrase is recognised.

    Intentionally conservative: we'd rather fall back to unfiltered semantic
    search than wrongly narrow the window. The vector-store layer converts
    these bounds to epoch seconds for Chroma's numeric comparators.
    """
    q = question.lower()
    today = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

    if "today" in q:
        return today, now_utc
    if "yesterday" in q:
        return today - timedelta(days=1), today
    if "last week" in q or "past week" in q or "this week" in q:
        return today - timedelta(days=7), now_utc
    if "last month" in q or "past month" in q or "this month" in q:
        return today - timedelta(days=30), now_utc
    if "last year" in q or "past year" in q:
        return today - timedelta(days=365), now_utc

    # "in 2023", "from 2022", "during 2021" → whole-year windows.
    year_match = re.search(r"\b(?:in|from|during)\s+(19|20)(\d{2})\b", q)
    if year_match:
        year = int(year_match.group(1) + year_match.group(2))
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        return start, end

    # Catch-all "recency" cues — checked last so explicit windows above still
    # win. "recent news on NVDA" → 30-day lookback.
    if any(phrase in q for phrase in _RECENCY_PHRASES):
        return today - timedelta(days=30), now_utc

    return None, None


def _extract_ticker_hint(question: str, known_tickers: set[str] | None = None) -> str | None:
    """Return a ticker symbol mentioned in the question, if one looks plausible.

    We only accept tokens already in ``known_tickers`` (populated lazily from
    the DB) to avoid false positives on common uppercase words like "I", "A",
    or "US". Returns ``None`` when nothing matches.
    """
    if not known_tickers:
        return None
    for token in _TICKER_RE.findall(question):
        if token in known_tickers:
            return token
    return None


# ---------------------------------------------------------------------------
# Query rewriter
#
# User questions like "how's apple doing?" are terrible retrieval queries:
# they're short, pronoun-heavy, miss the ticker, and lack temporal scope. The
# previous heuristic pipeline (``_parse_time_hints`` + ``_extract_ticker_hint``
# over the *raw* message) caught "last week" and "AAPL" when the user was
# explicit, but silently did nothing for "current sentiment on Apple".
#
# The rewriter runs a cheap, non-streaming LLM pass ahead of retrieval and
# returns structured hints: a search query tuned for semantic similarity
# against a financial news corpus, the ticker (if any), and a lookback window
# in days. We fail open — any JSON parse error, schema mismatch, or network
# hiccup falls back to the raw question + heuristic parsing so chat never
# breaks because of the rewriter.
# ---------------------------------------------------------------------------

_REWRITER_SYSTEM_PROMPT = """You rewrite user questions into optimal retrieval queries for a financial news vector store.

Given the conversation history and the user's latest question, produce a JSON object with these fields (and NOTHING else):
  - "search_query": a 5-20 word query string optimised for semantic similarity against news articles. Expand company names to include their ticker (e.g. Apple -> Apple AAPL), add 1-3 relevant domain terms (earnings, guidance, analyst upgrade, etc.), resolve pronouns from history, drop filler. Write in natural phrasing, NOT keyword soup.
  - "ticker": the single most relevant stock ticker (uppercase, 1-5 letters) the question is about, or null if none applies.
  - "lookback_days": integer window hint. 1 for "today"/"yesterday", 7 for "this week", 30 for "current"/"latest"/"recent"/general present-tense questions, 365 for "this year", null for questions about a specific past year or with no temporal dimension.
  - "year": the specific calendar year the question is about (e.g. 2023 for "NVDA in 2023") as an integer, or null otherwise.

Rules:
- Respond with ONLY the JSON object. No prose, no code fences.
- Never invent tickers that weren't in the question or the history.
- When lookback_days and year are both null, retrieval will be unfiltered in time - use that for timeless questions like "what does P/E ratio mean?"."""


def _extract_json_object(text: str) -> dict | None:
    """Pull the first ``{...}`` object out of a model response.

    Models sometimes wrap JSON in prose or triple-backticks even when asked
    not to. We greedily grab the outermost balanced ``{...}`` and parse it.
    Returns ``None`` on any failure so callers can fall back.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _window_from_rewrite(
    lookback_days: int | None, year: int | None, now_utc: datetime
) -> tuple[datetime | None, datetime | None]:
    """Translate the rewriter's structured time hints into a concrete window.

    ``year`` wins over ``lookback_days`` because a specific year is strictly
    more informative than a generic recency bucket.
    """
    if isinstance(year, int) and 1900 <= year <= 2100:
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        return start, end
    if isinstance(lookback_days, int) and lookback_days > 0:
        return now_utc - timedelta(days=lookback_days), now_utc
    return None, None


class RAGChatService:
    def __init__(self, vector_store: VectorStoreService | None = None):
        self._llm = ChatGroq(
            model=settings.GROQ_MODEL,
            api_key=settings.GROQ_API_KEY,
            temperature=0.3,
            streaming=True,
        )
        # Dedicated non-streaming, low-temperature instance for the rewriter.
        # Kept separate from ``self._llm`` so we can (a) swap it for a smaller
        # / faster model later without touching the main answer path and
        # (b) avoid any streaming overhead on a sub-second structured call.
        self._rewriter_llm = ChatGroq(
            model=settings.GROQ_MODEL,
            api_key=settings.GROQ_API_KEY,
            temperature=0.0,
            streaming=False,
        )
        self._vector_store = vector_store or VectorStoreService()
        # Cached set of known tickers, populated lazily on the first chat turn
        # so we don't hit the DB on every ``_extract_ticker_hint`` call.
        self._known_tickers: set[str] | None = None

    async def _load_known_tickers(self, db: AsyncSession) -> set[str]:
        if self._known_tickers is not None:
            return self._known_tickers
        from app.models import Company  # local import to avoid cycles

        result = await db.execute(select(Company.ticker_symbol))
        self._known_tickers = {row[0] for row in result.all() if row[0]}
        return self._known_tickers

    async def _load_social_snapshot(
        self, db: AsyncSession, ticker: str
    ) -> str | None:
        """Return a compact text block describing the latest social-sentiment
        snapshot for ``ticker``, or ``None`` if no data exists.

        The block is designed to drop straight into the LLM's context so the
        answer can reference buzz, bullish/bearish ratios, and trend without
        the user having to specifically ask about social media. Keeping it
        tiny (~5 lines) avoids eating into the retrieval budget.
        """
        from app.models import SocialSentiment  # local import to avoid cycles

        try:
            result = await db.execute(
                select(SocialSentiment)
                .where(SocialSentiment.ticker_symbol == ticker.upper())
                .order_by(SocialSentiment.fetched_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
        except Exception as exc:  # noqa: BLE001 — fail open, social is extra
            logger.warning("Social snapshot lookup failed for %s: %s", ticker, exc)
            return None

        if row is None:
            return None

        bullish = float(row.bullish_ratio or 0)
        bearish = float(row.bearish_ratio or 0)
        buzz = float(row.buzz_score or 0)
        volume = int(row.post_volume or 0)
        trend = (row.sentiment_trend or "flat").strip() or "flat"

        # 10-point deadband so a razor-thin edge doesn't flip the label.
        if bullish > bearish + 0.1:
            label = "bullish"
        elif bearish > bullish + 0.1:
            label = "bearish"
        else:
            label = "mixed"

        fetched_at = (
            row.fetched_at.strftime("%Y-%m-%d %H:%M UTC")
            if row.fetched_at
            else "unknown"
        )

        return (
            f"[Live social signal for {ticker.upper()} | snapshot {fetched_at}]\n"
            f"- Overall retail chatter: {label}\n"
            f"- Bullish share: {bullish * 100:.0f}% | "
            f"Bearish share: {bearish * 100:.0f}%\n"
            f"- Buzz score: {buzz:.1f} | Post volume (latest window): "
            f"{volume:,}\n"
            f"- Trend vs previous snapshot: {trend}"
        )

    async def _rewrite_query(
        self,
        user_message: str,
        history_rows: list[ChatMessage],
        known_tickers: set[str],
        now_utc: datetime,
    ) -> dict:
        """Ask the LLM to rewrite the user's question into a retrieval-
        optimised form plus structured hints.

        Returns a dict with keys ``search_query`` (str), ``ticker``
        (str | None), ``since`` (datetime | None), ``until`` (datetime | None).
        Falls back to the raw question + heuristic hints on any failure so a
        flaky rewriter never breaks chat.
        """
        # Fallback result we'll return on any error path. Mirrors the old
        # heuristic pipeline exactly so behaviour before/after this change is
        # identical when the rewriter is unavailable.
        since, until = _parse_time_hints(user_message, now_utc)
        fallback: dict = {
            "search_query": user_message,
            "ticker": _extract_ticker_hint(user_message, known_tickers),
            "since": since,
            "until": until,
        }

        # Build a trimmed history block — last 4 turns is plenty of pronoun
        # context without blowing up the token budget.
        history_snippets: list[str] = []
        for msg in history_rows[-4:]:
            role = "User" if msg.role == "user" else "Assistant"
            snippet = (msg.content or "")[:300]
            history_snippets.append(f"{role}: {snippet}")
        history_block = "\n".join(history_snippets) or "(no prior turns)"

        user_payload = (
            f"Today's date: {now_utc.strftime('%Y-%m-%d')} (UTC)\n\n"
            f"Conversation so far:\n{history_block}\n\n"
            f"Latest user question: {user_message}\n\n"
            f"Return the JSON object now."
        )

        try:
            response = await self._rewriter_llm.ainvoke(
                [
                    SystemMessage(content=_REWRITER_SYSTEM_PROMPT),
                    HumanMessage(content=user_payload),
                ]
            )
        except Exception as exc:  # noqa: BLE001 — fail open
            logger.warning("Query rewriter call failed, using raw question: %s", exc)
            return fallback

        raw = (response.content or "").strip() if hasattr(response, "content") else ""
        parsed = _extract_json_object(raw)
        if not parsed:
            logger.warning("Query rewriter returned unparseable output: %r", raw[:200])
            return fallback

        search_query = parsed.get("search_query")
        if not isinstance(search_query, str) or not search_query.strip():
            search_query = user_message

        ticker = parsed.get("ticker")
        if isinstance(ticker, str):
            ticker = ticker.strip().upper() or None
            # Only trust tickers that actually exist in our universe — the
            # rewriter can hallucinate plausible-looking symbols.
            if ticker and ticker not in known_tickers:
                logger.info("Rewriter proposed unknown ticker %r; dropping", ticker)
                ticker = None
        else:
            ticker = None

        lookback_days = parsed.get("lookback_days")
        year = parsed.get("year")
        r_since, r_until = _window_from_rewrite(lookback_days, year, now_utc)

        logger.info(
            "Rewrote chat query: raw=%r -> search=%r ticker=%s since=%s until=%s",
            user_message[:120],
            search_query[:120],
            ticker,
            r_since,
            r_until,
        )

        return {
            "search_query": search_query.strip(),
            "ticker": ticker,
            "since": r_since,
            "until": r_until,
        }

    async def chat(
        self,
        session_id: int,
        user_message: str,
        db: AsyncSession,
    ) -> AsyncGenerator[dict, None]:
        """Stream a chat turn.

        Yields dicts of shape ``{"token": str}`` or ``{"citations": [...]}``.
        The caller is responsible for JSON-encoding them before sending over SSE.
        """
        session = await db.get(ChatSession, session_id)
        if not session:
            raise ValueError(f"Chat session {session_id} not found")

        # Load recent chat history BEFORE persisting the new user message so it
        # isn't duplicated in the LLM turn (we append the current question
        # explicitly below with retrieved context attached).
        history_result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(10)
        )
        history_rows = list(reversed(history_result.scalars().all()))

        # Persist the user message now that history is captured.
        user_msg = ChatMessage(
            session_id=session_id,
            role="user",
            content=user_message,
        )
        db.add(user_msg)
        await db.flush()

        # Resolve the "now" for temporal hints in the current question. We keep
        # it as one value so the system prompt and the time filters stay
        # consistent even across a slow retrieval.
        now_utc = datetime.now(timezone.utc)
        known_tickers = await self._load_known_tickers(db)

        # Pre-parse step: run the raw user question through a cheap LLM pass
        # that rewrites it into a retrieval-optimised query and returns
        # structured ticker/time hints. This catches cases the pure regex
        # heuristics miss (pronoun resolution, company-name -> ticker
        # expansion, implicit recency). Fails open to the raw question.
        rewrite = await self._rewrite_query(
            user_message=user_message,
            history_rows=history_rows,
            known_tickers=known_tickers,
            now_utc=now_utc,
        )
        search_query = rewrite["search_query"]
        since = rewrite["since"]
        until = rewrite["until"]
        ticker_hint = rewrite["ticker"]

        # Retrieve relevant docs, preferring a ticker/time-scoped search when
        # the question contains obvious hints. If the filtered query yields
        # nothing we fall back to unfiltered semantic search so the user
        # still gets *some* grounding context.
        retrieved = self._vector_store.search(
            search_query,
            n_results=5,
            since=since,
            until=until,
            ticker=ticker_hint,
        )
        if not retrieved and (since or until or ticker_hint):
            logger.info(
                "Filtered chat retrieval empty (ticker=%s, since=%s, until=%s); "
                "falling back to unfiltered search",
                ticker_hint,
                since,
                until,
            )
            retrieved = self._vector_store.search(search_query, n_results=5)

        context_parts: list[str] = []
        citations: list[dict] = []
        for hit in retrieved:
            meta = hit.get("metadata", {})
            doc_text = hit.get("document", "")
            source_label = meta.get("source", meta.get("ticker", "unknown"))
            pub_date = meta.get("publication_date") or "date unknown"
            ticker = meta.get("ticker") or ""
            ticker_tag = f" {ticker}" if ticker else ""
            # Prefix every chunk with ``[source TICKER | YYYY-MM-DD]`` so the
            # LLM can cite dates verbatim instead of guessing.
            context_parts.append(
                f"[{source_label}{ticker_tag} | {pub_date}] {doc_text}"
            )
            citations.append(
                {
                    "id": hit.get("id", ""),
                    "title": meta.get("title", source_label),
                    "source": source_label,
                    "url": meta.get("url", ""),
                    "type": meta.get("type", ""),
                    "publication_date": meta.get("publication_date", ""),
                    "ticker": ticker,
                }
            )

        # When the user's question is ticker-scoped, fetch the latest social
        # sentiment snapshot from Postgres and prepend it to the retrieved
        # context. This gives the LLM live retail-chatter signal it would
        # otherwise never see — Chroma only carries historical news text,
        # not the aggregated bullish/bearish/buzz stats.
        social_block: str | None = None
        if ticker_hint:
            social_block = await self._load_social_snapshot(db, ticker_hint)

        if social_block and context_parts:
            context_block = social_block + "\n\n" + "\n\n".join(context_parts)
        elif social_block:
            context_block = (
                social_block
                + "\n\nNo relevant news articles were retrieved for this query."
            )
        elif context_parts:
            context_block = "\n\n".join(context_parts)
        else:
            context_block = "No relevant documents found."

        messages: list = [
            SystemMessage(content=_build_system_prompt(now_utc)),
        ]
        for msg in history_rows:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))

        messages.append(
            HumanMessage(
                content=(
                    f"Retrieved context:\n{context_block}\n\n"
                    f"User question: {user_message}"
                )
            )
        )

        # Emit citations once up-front so the client can render them while
        # tokens stream in.
        yield {"citations": citations}

        full_response: list[str] = []
        async for chunk in self._llm.astream(messages):
            token = chunk.content
            if token:
                full_response.append(token)
                yield {"token": token}

        # Persist assistant response.
        assistant_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content="".join(full_response),
            citations=citations,
        )
        db.add(assistant_msg)
        await db.flush()
