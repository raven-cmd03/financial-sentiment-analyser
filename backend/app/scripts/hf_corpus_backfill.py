"""CLI entry point for the HuggingFace-corpus news backfill.

Pulls ticker-tagged historical news from the gated
``Brianferrell787/financial-news-multisource`` dataset (57M rows,
1999–2025). The 4 ticker-tagged subsets combined are ~5M rows; expect
a full run to take 1–3 hours depending on disk / network, and to land
roughly 10k–200k articles per popular ticker in the DB.

Usage (from inside the backend container)::

    docker compose exec backend python -m app.scripts.hf_corpus_backfill \\
        --tickers AAPL,MSFT --subsets fnspid_news --max-rows 500000

Common flags::

    --tickers AAPL,MSFT        Only match these symbols (default: every
                               Company row). Symbols are uppercased.
    --subsets a,b,c            Subsets to stream (default: all 4 tagged
                               subsets). Valid values:
                               fnspid_news, benzinga_6000stocks,
                               yahoo_finance_felixdrinkall,
                               sentarl_combined
    --start-date YYYY-MM-DD    Earliest publication date to keep
    --end-date YYYY-MM-DD      Latest publication date to keep
    --max-rows N               Per-subset scan cap (default: no cap)
    --batch-size N             Articles per persist+dispatch (default 200)
    --no-sentiment             Persist only; skip FinBERT dispatch
    --progress-every N         Log a heartbeat every N scanned rows
                               (default 50000)

Prerequisites:

* ``HUGGINGFACE_API_KEY`` set in ``.env``.
* Dataset's research-use terms accepted on hf.co (one-time click).
* ``datasets`` installed (already in requirements).

Exit codes: ``0`` on success even if some subsets failed (partial
progress still valuable); ``1`` on config error or unhandled exception.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime

logger = logging.getLogger("hf_corpus_backfill")


_VALID_SUBSETS = (
    "fnspid_news",
    "benzinga_6000stocks",
    "yahoo_finance_felixdrinkall",
    "sentarl_combined",
)


def _parse_date(value: str) -> datetime:
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"Invalid date {value!r} — expected YYYY-MM-DD or ISO 8601"
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.scripts.hf_corpus_backfill",
        description=(
            "Backfill news_articles from the Brianferrell787/"
            "financial-news-multisource HF dataset (ticker-tagged subsets only)."
        ),
    )
    parser.add_argument(
        "--tickers",
        help="Comma-separated ticker symbols. Default: every Company row.",
        default=None,
    )
    parser.add_argument(
        "--subsets",
        help=(
            f"Comma-separated subset names (choices: {', '.join(_VALID_SUBSETS)}). "
            "Default: all 4."
        ),
        default=None,
    )
    parser.add_argument(
        "--start-date",
        type=_parse_date,
        default=None,
        help="Earliest publication date to keep (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--end-date",
        type=_parse_date,
        default=None,
        help="Latest publication date to keep (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Per-subset scan cap. Default: no cap.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Articles per persist+dispatch batch (default: 200).",
    )
    parser.add_argument(
        "--no-sentiment",
        action="store_true",
        help="Persist articles but don't enqueue FinBERT analysis.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=50_000,
        help="Log a progress line every N scanned rows (default: 50000).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    args = _parse_args(argv)

    tickers = None
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        if not tickers:
            logger.error("--tickers was empty after parsing")
            return 1

    subsets = None
    if args.subsets:
        subsets = [s.strip() for s in args.subsets.split(",") if s.strip()]
        invalid = [s for s in subsets if s not in _VALID_SUBSETS]
        if invalid:
            logger.error(
                "Unknown subsets: %s. Valid: %s",
                ", ".join(invalid),
                ", ".join(_VALID_SUBSETS),
            )
            return 1

    from app.clients import HFCorpusError
    from app.services.hf_corpus_backfill import run_hf_corpus_backfill

    try:
        summary = run_hf_corpus_backfill(
            tickers=tickers,
            subsets=subsets,
            start_date=args.start_date,
            end_date=args.end_date,
            max_rows_per_subset=args.max_rows,
            batch_size=args.batch_size,
            dispatch_sentiment=not args.no_sentiment,
            progress_every=args.progress_every,
        )
    except HFCorpusError as exc:
        logger.error("HF backfill failed: %s", exc)
        return 1
    except Exception:
        logger.exception("HF backfill failed (unhandled)")
        return 1

    print(json.dumps(summary.as_dict(), indent=2, default=str))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI shim
    sys.exit(main())
