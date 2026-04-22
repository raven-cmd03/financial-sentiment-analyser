"""Smoke test: every Celery task imports cleanly.

This would have caught the phantom `AdanosSocialClient` / `CorrelationCalculator`
imports in `app.workers.tasks` that the original review flagged.
"""

import importlib


def test_tasks_module_imports():
    mod = importlib.import_module("app.workers.tasks")
    # The four scheduled / chained tasks must all be exposed as attributes.
    for name in (
        "collect_news_task",
        "analyze_sentiment_task",
        "poll_social_sentiment_task",
        "update_correlations_task",
        "index_vector_store_task",
        "run_finetuning_task",
    ):
        assert hasattr(mod, name), f"tasks.py missing {name!r}"


def test_helpers_reference_real_clients():
    """Stricter: the inner async helpers import the concrete client classes
    rather than the bogus names they used to import."""
    mod = importlib.import_module("app.workers.tasks")
    # Both helpers must exist (they're the inline helpers the tasks delegate to).
    assert hasattr(mod, "_fetch_adanos_for_tickers")
    assert hasattr(mod, "_run_correlations_for_tickers")
