"""FinBERT-style sentiment analyzer.

The class is label-agnostic: it reads ``model.config.id2label`` from the
loaded HuggingFace checkpoint and builds a semantic-label → class-index
map on the fly. This means swapping between models with different class
orderings — e.g. ``ProsusAI/finbert`` (``positive, negative, neutral``)
and ``yiyanghkust/finbert-tone`` (``neutral, positive, negative``) —
"just works" without any code change. Fine-tuned checkpoints that ship
their own ``id2label`` in ``config.json`` are handled the same way.
"""

import logging
import re
from html import unescape

import torch
from transformers import (
    AutoConfig,
    AutoTokenizer,
    AutoModelForSequenceClassification,
    BertConfig,
    BertForSequenceClassification,
    BertTokenizer,
)

from app.config import get_settings

logger = logging.getLogger(__name__)

# Three canonical labels the rest of the system expects. Everything from
# the model's id2label gets normalised onto one of these via fuzzy match
# (lowercased, stripped of punctuation / whitespace).
_CANONICAL_LABELS = ("positive", "negative", "neutral")

# Fallback used only when the model config is missing an id2label (very
# rare — most HF classification checkpoints set it). Preserves the
# ProsusAI/finbert ordering, which was the historic assumption.
_FALLBACK_LABEL_ORDER = ("positive", "negative", "neutral")

# Explicit per-repo overrides for models that publish only generic
# ``LABEL_0/1/2`` in their config.json — auto-detection can't help us
# there because ``LABEL_N`` carries no semantics. Keyed by HF repo id.
# Sources: the official model cards on huggingface.co.
_KNOWN_LABEL_MAPS: dict[str, dict[str, int]] = {
    # yiyanghkust/finbert-tone: "LABEL_0: neutral; LABEL_1: positive;
    # LABEL_2: negative" — from the model card's published snippet.
    "yiyanghkust/finbert-tone": {
        "neutral": 0,
        "positive": 1,
        "negative": 2,
    },
    # ProsusAI/finbert: {0: positive, 1: negative, 2: neutral} — ships
    # with proper id2label, but we pin it anyway so auto-detection and
    # the override table agree (useful if someone strips configs).
    "ProsusAI/finbert": {
        "positive": 0,
        "negative": 1,
        "neutral": 2,
    },
    # ahmedrachid/FinancialBERT-Sentiment-Analysis: {0: negative,
    # 1: neutral, 2: positive} per its config.json.
    "ahmedrachid/FinancialBERT-Sentiment-Analysis": {
        "negative": 0,
        "neutral": 1,
        "positive": 2,
    },
}


def _canonicalise(raw: str) -> str | None:
    """Map an arbitrary id2label value onto one of our canonical labels."""
    if not raw:
        return None
    key = re.sub(r"[^a-z]", "", raw.lower())
    # Handle a few common variants people ship in fine-tuned configs.
    alias = {
        "bullish": "positive",
        "pos": "positive",
        "positive": "positive",
        "bearish": "negative",
        "neg": "negative",
        "negative": "negative",
        "neu": "neutral",
        "neutral": "neutral",
        "somewhatbullish": "positive",
        "somewhatbearish": "negative",
    }
    return alias.get(key)


def _build_label_index(model, model_name: str | None = None) -> dict[str, int]:
    """Return a ``{canonical_label: class_index}`` map.

    Resolution order:

    1. ``_KNOWN_LABEL_MAPS[model_name]`` — explicit overrides for models
       that ship only ``LABEL_N`` placeholders in their ``config.json``
       (e.g. ``yiyanghkust/finbert-tone``). Auto-detection is impossible
       for those because the label strings carry no semantics.
    2. ``model.config.id2label`` — HF's built-in. Values are canonicalised
       onto ``positive``/``negative``/``neutral`` via ``_canonicalise``.
    3. ProsusAI positional fallback — last resort, loud warning.
    """
    if model_name and model_name in _KNOWN_LABEL_MAPS:
        index = dict(_KNOWN_LABEL_MAPS[model_name])
        logger.info(
            "Using pinned label map for %s: %s", model_name, index
        )
        return index

    id2label = getattr(model.config, "id2label", None) or {}
    index: dict[str, int] = {}

    for idx, raw in id2label.items():
        canonical = _canonicalise(str(raw))
        if canonical and canonical not in index:
            index[canonical] = int(idx)

    missing = [lbl for lbl in _CANONICAL_LABELS if lbl not in index]
    if missing:
        logger.warning(
            "Model %r id2label=%s missing canonical labels %s; "
            "using positional fallback. Add an entry to _KNOWN_LABEL_MAPS "
            "if this model ships only LABEL_N placeholders.",
            model_name or "<unknown>",
            id2label,
            missing,
        )
        for pos, lbl in enumerate(_FALLBACK_LABEL_ORDER):
            index.setdefault(lbl, pos)

    logger.info("Resolved label-to-index map: %s", index)
    return index


def _load_tokenizer(model_name: str):
    """Load a tokenizer with graceful fast→slow fallback.

    Several finance checkpoints on the Hub (notably
    ``yiyanghkust/finbert-tone``) ship only a WordPiece ``vocab.txt`` and
    no ``tokenizer.json``. AutoTokenizer tries to build the fast variant
    by default and raises a confusing
    "Couldn't instantiate the backend tokenizer" ValueError even when
    ``use_fast=False`` is passed (because the slow→fast conversion is
    still attempted internally). The reliable fix is to dispatch to the
    tokenizer class named in ``config.json`` directly.
    """
    # Path 1: the normal happy path — works for almost every HF model.
    try:
        return AutoTokenizer.from_pretrained(model_name)
    except (ValueError, OSError) as exc:
        logger.info(
            "Fast tokenizer load failed for %s (%s); trying slow",
            model_name,
            exc.__class__.__name__,
        )

    # Path 2: explicit slow-tokenizer request via AutoTokenizer.
    try:
        return AutoTokenizer.from_pretrained(model_name, use_fast=False)
    except (ValueError, OSError) as exc:
        logger.info(
            "Slow AutoTokenizer also failed for %s (%s); dispatching by class",
            model_name,
            exc.__class__.__name__,
        )

    # Path 3: consult the model's config. Some checkpoints (e.g.
    # yiyanghkust/finbert-tone) ship an incomplete config.json that
    # lacks ``model_type``, so AutoConfig itself raises. Swallow that
    # and fall through to the BertTokenizer path, which is the right
    # choice for every BERT-derived finance model we expect to see.
    cls_name = ""
    model_type = ""
    try:
        config = AutoConfig.from_pretrained(model_name)
        cls_name = getattr(config, "tokenizer_class", None) or ""
        model_type = getattr(config, "model_type", "") or ""
    except (ValueError, OSError) as exc:
        logger.info(
            "AutoConfig failed for %s (%s); assuming BERT-family",
            model_name,
            exc.__class__.__name__,
        )

    if (
        not cls_name
        or "bert" in cls_name.lower()
        or model_type == "bert"
    ):
        return BertTokenizer.from_pretrained(model_name)

    raise RuntimeError(
        f"Could not load a tokenizer for {model_name!r}; "
        f"tokenizer_class={cls_name!r}, model_type={model_type!r}"
    )


def _load_model(model_name: str):
    """Load a classification model with graceful fallback.

    Mirrors ``_load_tokenizer``: some checkpoints on HF ship an
    incomplete ``config.json`` (missing ``model_type``) that breaks
    AutoConfig/AutoModel resolution. For BERT-family finance models we
    can reliably fall back to the concrete Bert class.
    """
    try:
        return AutoModelForSequenceClassification.from_pretrained(model_name)
    except (ValueError, OSError) as exc:
        logger.info(
            "AutoModel load failed for %s (%s); trying BertForSequenceClassification",
            model_name,
            exc.__class__.__name__,
        )

    # Load config via BertConfig (doesn't require model_type).
    config = BertConfig.from_pretrained(model_name)
    return BertForSequenceClassification.from_pretrained(
        model_name, config=config
    )


class SentimentAnalyzer:
    def __init__(self, model_name: str | None = None):
        settings = get_settings()
        self.model_name = model_name or settings.FINBERT_MODEL
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(
            "Loading sentiment model %s on %s", self.model_name, self.device
        )
        self.tokenizer = _load_tokenizer(self.model_name)
        self.model = _load_model(self.model_name).to(self.device)
        self.model.eval()
        self._label_index = _build_label_index(self.model, self.model_name)
        logger.info("Sentiment model loaded successfully")

    # ------------------------------------------------------------------
    # Text preprocessing
    # ------------------------------------------------------------------

    def _preprocess(self, text: str) -> str:
        text = unescape(text)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        # Truncation is handled by the tokenizer in analyze()/batch_analyze()
        # via truncation=True, max_length=512 — don't double-truncate here.
        return text

    def _probs_to_result(self, prob: torch.Tensor) -> dict:
        pos_idx = self._label_index["positive"]
        neg_idx = self._label_index["negative"]
        neu_idx = self._label_index["neutral"]

        positive = prob[pos_idx].item()
        negative = prob[neg_idx].item()
        neutral = prob[neu_idx].item()

        scores = {"positive": positive, "negative": negative, "neutral": neutral}
        label = max(scores, key=scores.get)
        confidence = scores[label]

        return {
            "sentiment_label": label,
            "positive_score": round(positive, 4),
            "negative_score": round(negative, 4),
            "neutral_score": round(neutral, 4),
            "confidence": round(confidence, 4),
        }

    # ------------------------------------------------------------------
    # Single inference
    # ------------------------------------------------------------------

    def analyze(self, text: str) -> dict:
        """Return sentiment scores for a single text."""
        text = self._preprocess(text)
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1).squeeze()

        return self._probs_to_result(probs)

    # ------------------------------------------------------------------
    # Batch inference
    # ------------------------------------------------------------------

    def batch_analyze(self, texts: list[str], batch_size: int = 16) -> list[dict]:
        """Process a list of texts in fixed-size batches."""
        results: list[dict] = []
        preprocessed = [self._preprocess(t) for t in texts]

        for start in range(0, len(preprocessed), batch_size):
            batch = preprocessed[start : start + batch_size]
            inputs = self.tokenizer(
                batch,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True,
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = torch.nn.functional.softmax(outputs.logits, dim=-1)

            for prob in probs:
                results.append(self._probs_to_result(prob))

        return results

    # ------------------------------------------------------------------
    # Hot-swap
    # ------------------------------------------------------------------

    def hot_swap_model(self, model_path: str) -> None:
        """Load a fine-tuned checkpoint at runtime without restarting the server."""
        logger.info("Hot-swapping model to %s", model_path)
        try:
            new_tokenizer = _load_tokenizer(model_path)
            new_model = _load_model(model_path).to(self.device)
            new_model.eval()

            self.tokenizer = new_tokenizer
            self.model = new_model
            self.model_name = model_path
            # Label order can change across checkpoints — always rebuild.
            self._label_index = _build_label_index(self.model, self.model_name)
            logger.info("Model hot-swapped successfully to %s", model_path)
        except Exception:
            logger.exception("Failed to hot-swap model from %s", model_path)
            raise
