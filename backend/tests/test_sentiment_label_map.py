"""Tests for the label-map auto-detection in SentimentAnalyzer.

These verify that swapping between models with different class
orderings — e.g. ProsusAI/finbert vs yiyanghkust/finbert-tone — keeps
the output semantics correct without hand-editing LABEL_MAP.

The tests mock out the HF load path so they don't pull any weights
across the network.
"""

from __future__ import annotations

from types import SimpleNamespace

import torch

from app.services.sentiment_analyzer import _build_label_index, _canonicalise


def test_canonicalise_handles_common_variants() -> None:
    assert _canonicalise("Positive") == "positive"
    assert _canonicalise("POSITIVE") == "positive"
    assert _canonicalise("Bullish") == "positive"
    assert _canonicalise("Somewhat-Bullish") == "positive"
    assert _canonicalise("Negative") == "negative"
    assert _canonicalise("Bearish") == "negative"
    assert _canonicalise("Neutral") == "neutral"
    assert _canonicalise("neu") == "neutral"
    assert _canonicalise("") is None
    assert _canonicalise("gibberish") is None


def test_build_label_index_prosus_ordering() -> None:
    # ProsusAI/finbert: {0: positive, 1: negative, 2: neutral}
    model = SimpleNamespace(
        config=SimpleNamespace(
            id2label={0: "positive", 1: "negative", 2: "neutral"}
        )
    )
    idx = _build_label_index(model)
    assert idx == {"positive": 0, "negative": 1, "neutral": 2}


def test_build_label_index_finbert_tone_ordering() -> None:
    # yiyanghkust/finbert-tone: {0: neutral, 1: positive, 2: negative}
    model = SimpleNamespace(
        config=SimpleNamespace(
            id2label={0: "Neutral", 1: "Positive", 2: "Negative"}
        )
    )
    idx = _build_label_index(model)
    assert idx == {"neutral": 0, "positive": 1, "negative": 2}


def test_build_label_index_falls_back_when_id2label_missing() -> None:
    model = SimpleNamespace(config=SimpleNamespace())
    idx = _build_label_index(model)
    # Fallback preserves ProsusAI's historic ordering so something still
    # works rather than crashing — a warning is logged at call-time.
    assert idx == {"positive": 0, "negative": 1, "neutral": 2}


def test_build_label_index_uses_pinned_map_for_finbert_tone() -> None:
    """finbert-tone ships LABEL_0/1/2 instead of semantic names — the
    pinned override in _KNOWN_LABEL_MAPS is the only correct source.
    """
    # Even if the model (weirdly) reports semantic labels, the override
    # should win because the HF card is the authoritative source.
    model = SimpleNamespace(
        config=SimpleNamespace(
            id2label={0: "LABEL_0", 1: "LABEL_1", 2: "LABEL_2"}
        )
    )
    idx = _build_label_index(model, "yiyanghkust/finbert-tone")
    assert idx == {"neutral": 0, "positive": 1, "negative": 2}


def test_build_label_index_pinned_map_for_prosus() -> None:
    model = SimpleNamespace(config=SimpleNamespace())
    idx = _build_label_index(model, "ProsusAI/finbert")
    assert idx == {"positive": 0, "negative": 1, "neutral": 2}


def test_build_label_index_pinned_map_for_ahmedrachid() -> None:
    model = SimpleNamespace(config=SimpleNamespace())
    idx = _build_label_index(
        model, "ahmedrachid/FinancialBERT-Sentiment-Analysis"
    )
    assert idx == {"negative": 0, "neutral": 1, "positive": 2}


def test_probs_to_result_is_correct_for_finbert_tone_order() -> None:
    """Smoke-test the end-to-end mapping using a stub model.

    We don't load FinBERT here; we just verify that ``_probs_to_result``
    looks up the right class index regardless of positional ordering.
    """
    from app.services.sentiment_analyzer import SentimentAnalyzer

    # Build an analyzer by hand without __init__ (which would hit HF).
    analyzer = SentimentAnalyzer.__new__(SentimentAnalyzer)
    analyzer._label_index = {"neutral": 0, "positive": 1, "negative": 2}

    # finbert-tone layout: position 0 neutral, 1 positive, 2 negative.
    # A strongly-positive probability vector should yield label=positive.
    probs = torch.tensor([0.05, 0.90, 0.05])
    result = analyzer._probs_to_result(probs)
    assert result["sentiment_label"] == "positive"
    assert result["positive_score"] == 0.9
    assert result["neutral_score"] == 0.05
    assert result["negative_score"] == 0.05
    assert result["confidence"] == 0.9

    # Same analyzer — now a strongly-negative vector.
    probs = torch.tensor([0.1, 0.05, 0.85])
    result = analyzer._probs_to_result(probs)
    assert result["sentiment_label"] == "negative"
    assert result["negative_score"] == 0.85


def test_probs_to_result_prosus_ordering() -> None:
    """Same semantics with ProsusAI's position ordering — must match."""
    from app.services.sentiment_analyzer import SentimentAnalyzer

    analyzer = SentimentAnalyzer.__new__(SentimentAnalyzer)
    analyzer._label_index = {"positive": 0, "negative": 1, "neutral": 2}

    # ProsusAI layout: position 0 positive, 1 negative, 2 neutral.
    # Strongly-positive vector.
    probs = torch.tensor([0.90, 0.05, 0.05])
    result = analyzer._probs_to_result(probs)
    assert result["sentiment_label"] == "positive"
    assert result["positive_score"] == 0.9
