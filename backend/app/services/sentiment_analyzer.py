import logging
import re
from html import unescape

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from app.config import get_settings

logger = logging.getLogger(__name__)

LABEL_MAP = {0: "positive", 1: "negative", 2: "neutral"}


class SentimentAnalyzer:
    def __init__(self, model_name: str | None = None):
        settings = get_settings()
        self.model_name = model_name or settings.FINBERT_MODEL
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("Loading FinBERT model %s on %s", self.model_name, self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name
        ).to(self.device)
        self.model.eval()
        logger.info("FinBERT model loaded successfully")

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

        positive = probs[0].item()
        negative = probs[1].item()
        neutral = probs[2].item()
        confidence = max(positive, negative, neutral)
        label = LABEL_MAP[int(probs.argmax())]

        return {
            "sentiment_label": label,
            "positive_score": round(positive, 4),
            "negative_score": round(negative, 4),
            "neutral_score": round(neutral, 4),
            "confidence": round(confidence, 4),
        }

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
                positive = prob[0].item()
                negative = prob[1].item()
                neutral = prob[2].item()
                confidence = max(positive, negative, neutral)
                label = LABEL_MAP[int(prob.argmax())]
                results.append(
                    {
                        "sentiment_label": label,
                        "positive_score": round(positive, 4),
                        "negative_score": round(negative, 4),
                        "neutral_score": round(neutral, 4),
                        "confidence": round(confidence, 4),
                    }
                )

        return results

    # ------------------------------------------------------------------
    # Hot-swap
    # ------------------------------------------------------------------

    def hot_swap_model(self, model_path: str) -> None:
        """Load a fine-tuned checkpoint at runtime without restarting the server."""
        logger.info("Hot-swapping model to %s", model_path)
        try:
            new_tokenizer = AutoTokenizer.from_pretrained(model_path)
            new_model = AutoModelForSequenceClassification.from_pretrained(
                model_path
            ).to(self.device)
            new_model.eval()

            self.tokenizer = new_tokenizer
            self.model = new_model
            self.model_name = model_path
            logger.info("Model hot-swapped successfully to %s", model_path)
        except Exception:
            logger.exception("Failed to hot-swap model from %s", model_path)
            raise
