"""Streaming reader for the ``Brianferrell787/financial-news-multisource``
HuggingFace dataset.

The corpus is 57M rows across 24 subsets (21 GB Parquet). For our backfill
we only touch the subsets that ship an explicit ``stocks`` (or
``mentioned_companies``) list in their ``extra_fields`` JSON blob — those
are the only ones we can map to a specific ticker without fuzzy text
matching. The other 19 subsets are general-news noise from our POV.

The reader is deliberately sync and single-subset-at-a-time: the HF
``datasets`` library is sync under the hood, and streaming one subset
keeps memory flat regardless of total corpus size. The caller filters
rows client-side by ticker set — the library has no server-side JSON
filter — so expect to iterate 4–5M rows to find a few tens of
thousands of matches. On a typical run that's ~15–30 min per subset.

Prerequisites:

* ``HUGGINGFACE_API_KEY`` set and the dataset's research-use terms
  accepted on hf.co.
* ``datasets`` + ``huggingface_hub`` installed (already in
  ``requirements.txt``).

Schema (input, per the dataset card)::

    {
        "date": "2020-06-05T06:30:54Z",   # ISO 8601 UTC
        "text": "Headline\\n\\nOptional body…",
        "extra_fields": "{\\"stocks\\": [\\"AAPL\\"], \\"url\\": ...}"
    }

Schema (output of ``_normalize`` — matches ``_persist_articles_sync``)::

    {
        "title": str,                # first paragraph of text, <=400 chars
        "content": str,              # rest of text, <=10k chars at persist
        "url": str,                  # real URL, or synthetic "hf://..." fallback
        "publication_date": str,     # ISO 8601 UTC, use date_trading if present
        "source": str,               # publisher name or subset label
        "tickers": list[str],        # uppercase, $-stripped
    }
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Iterator

logger = logging.getLogger(__name__)

# Fixed repo. Keeping it a constant (rather than a param) so the client's
# filter heuristics and the synthetic-URL scheme can assume the dataset's
# schema without a config lookup.
HF_DATASET_REPO = "Brianferrell787/financial-news-multisource"

# Only subsets that carry per-row ticker tags — extra_fields.stocks or
# extra_fields.mentioned_companies. These are the only ones worth
# streaming for a ticker-scoped backfill.
#
# Rough coverage (approximate; see dataset card):
#
#   fnspid_news                 1999-2023 — Benzinga, minute-level, ~4M rows,
#                               has ``stocks`` list.
#   benzinga_6000stocks         ~2000s-2010s — Benzinga analyst-ratings,
#                               has ``stocks`` list.
#   yahoo_finance_felixdrinkall 2017-2023 — Yahoo Finance full article,
#                               has ``stocks`` + ``mentioned_companies``.
#   sentarl_combined            1997-2020 — 20 big-cap assets, minute-level,
#                               has ``stocks`` list (mixed with index tickers
#                               like $SPX, $INDU — stripped to SPX, INDU).
TICKER_TAGGED_SUBSETS: tuple[str, ...] = (
    "fnspid_news",
    "benzinga_6000stocks",
    "yahoo_finance_felixdrinkall",
    "sentarl_combined",
)


class HFCorpusError(RuntimeError):
    """Raised when the HF dataset cannot be reached (401, network, etc)."""


class HFCorpusClient:
    """Streaming reader for ticker-tagged subsets.

    Parameters
    ----------
    token
        HuggingFace read token. If empty/None, gated datasets will fail
        with a 401 on first access — we raise ``HFCorpusError`` early
        so callers can surface a friendly message.
    """

    def __init__(self, token: str | None = None) -> None:
        self.token = (token or "").strip() or None
        if not self.token:
            logger.warning(
                "HFCorpusClient instantiated without a token — gated "
                "datasets will 401. Set HUGGINGFACE_API_KEY in .env."
            )

    def stream_subset(self, subset: str) -> Iterator[dict]:
        """Yield normalized article dicts from one subset.

        Rows with empty text or no usable date are skipped silently.
        Rows that fail to parse ``extra_fields`` still yield with
        ``tickers=[]`` so the caller can fall back to text search if
        it wants to.
        """
        try:
            # Lazy import so unit tests can stub the module without
            # the real ``datasets`` dependency installed.
            from datasets import load_dataset
        except ImportError as exc:  # pragma: no cover - deps-check
            raise HFCorpusError(
                "The 'datasets' package is required. Install with "
                "`pip install datasets>=2.18.0`."
            ) from exc

        try:
            ds = load_dataset(
                HF_DATASET_REPO,
                data_files=f"data/{subset}/*.parquet",
                split="train",
                streaming=True,
                token=self.token,
            )
        except Exception as exc:
            # 401 Unauthorized usually means the user hasn't accepted
            # the dataset's terms; wrap so the CLI can print a clear hint.
            msg = str(exc)
            if "401" in msg or "gated" in msg.lower():
                raise HFCorpusError(
                    f"Cannot access dataset '{HF_DATASET_REPO}' subset "
                    f"'{subset}'. Confirm you've (1) signed in, (2) accepted "
                    f"the dataset's research-use terms at "
                    f"https://huggingface.co/datasets/{HF_DATASET_REPO}, "
                    f"(3) set HUGGINGFACE_API_KEY. Underlying error: {exc}"
                ) from exc
            raise HFCorpusError(
                f"Failed to open subset '{subset}': {exc}"
            ) from exc

        for raw in ds:
            normalized = self._normalize(raw, subset)
            if normalized is not None:
                yield normalized

    # ------------------------------------------------------------------
    # Row normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(raw: dict, subset: str) -> dict | None:
        text = (raw.get("text") or "").strip()
        if not text:
            return None

        extra_raw = raw.get("extra_fields") or "{}"
        try:
            extra = json.loads(extra_raw) if isinstance(extra_raw, str) else dict(extra_raw)
        except (ValueError, TypeError):
            extra = {}

        tickers = _extract_tickers(extra)

        # Canonical text shape in our DB is "title\n\ncontent"; preserve
        # that by splitting on the first double-newline. Single-line
        # rows just become title with empty content.
        if "\n\n" in text:
            title_part, content_part = text.split("\n\n", 1)
            title = title_part.strip()
            content = content_part.strip()
        else:
            title = text
            content = ""

        if not title:
            return None

        url = _pick_url(extra)
        if not url:
            # Many rows (headline-only subsets, pre-Web archives) ship no
            # URL. We still want to persist them, but _persist_articles_sync
            # requires a non-empty URL for its article_id hash. A synthetic
            # scheme keeps the hash stable across re-runs and makes the
            # origin traceable in the DB.
            url = _synthetic_url(subset, raw.get("date") or "", text)

        pub_date = _pick_publication_date(raw, extra)
        source = _pick_source(extra, subset)

        return {
            "title": title,
            "content": content,
            "url": url,
            "publication_date": pub_date,
            "source": source,
            "tickers": tickers,
        }


# ---------------------------------------------------------------------------
# Helpers (module-level for easier unit testing)
# ---------------------------------------------------------------------------


def _extract_tickers(extra: dict) -> list[str]:
    """Pull ticker symbols from ``extra_fields``.

    Sources in priority order: ``stocks`` (primary field, present in all
    4 tagged subsets), then ``mentioned_companies`` (Yahoo Finance
    extras). Values are uppercased and the $ prefix used by sentarl for
    index tickers is stripped so ``$SPX`` becomes ``SPX``.

    Company-name placeholders like ``"AMERICAN_EXPRESS"`` (seen in
    reddit_finance_sp500) are preserved as-is; the caller should
    compare against its own ticker set and drop non-matches.
    """
    candidates: list[str] = []
    for key in ("stocks", "mentioned_companies"):
        value = extra.get(key)
        if isinstance(value, list):
            candidates.extend(v for v in value if isinstance(v, str))

    result: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        cleaned = raw.strip().lstrip("$").upper()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _pick_url(extra: dict) -> str:
    """Pick the most canonical URL from extras.

    Different subsets store URLs under different keys — try them in
    rough order of trustworthiness.
    """
    for key in ("url", "web_url", "link", "permalink"):
        value = extra.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _pick_publication_date(raw: dict, extra: dict) -> str | None:
    """Prefer ``date_trading`` (NYSE next-open) for day-level rows.

    Dataset card § Trading Date policy: day-level rows set top-level
    ``date`` to midnight UTC and keep the trading-session anchor in
    ``extra_fields.date_trading``. The trading anchor is the right
    value to line up news with the price series we already store (which
    is on a trading-day grid).
    """
    trading = extra.get("date_trading")
    if isinstance(trading, str) and trading:
        return trading
    top = raw.get("date")
    if isinstance(top, str) and top:
        return top
    return None


def _pick_source(extra: dict, subset: str) -> str:
    """Publisher/source string for the DB ``source`` column.

    Each subset tags either ``source`` (human-readable, e.g. "Benzinga",
    "CNBC") or ``publisher`` (more reliably set on web-scraped rows).
    Fall back to the subset name prefixed with ``hf:`` so operators
    can filter HF-sourced rows out in SQL if they ever want to.
    """
    for key in ("source", "publisher"):
        value = extra.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:100]
    return f"hf:{subset}"[:100]


def _synthetic_url(subset: str, date_str: str, text: str) -> str:
    """Synth a stable, unique URL for rows that ship without one.

    The hash is over ``(subset, date, first-400-chars-of-text)`` so
    re-streaming the same row produces the same URL → same
    ``article_id`` → dedup works on the existing unique index.
    """
    key = f"{subset}|{date_str}|{text[:400]}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"hf://{HF_DATASET_REPO}/{subset}#{digest}"
