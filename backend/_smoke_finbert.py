"""Throwaway smoke test for the new FinBERT — delete after verification.

Uses the exact sentences from the yiyanghkust/finbert-tone model card
so we can compare our outputs against what HF themselves publish.
"""
from app.services.sentiment_analyzer import SentimentAnalyzer


def main() -> None:
    print("Loading sentiment model (first run will download weights)...")
    a = SentimentAnalyzer()
    print(f"Model:  {a.model_name}")
    print(f"Device: {a.device}")
    print(f"Label-to-index map: {a._label_index}")
    print()

    # Sentences straight from the finbert-tone HF model card.
    cases = [
        ("negative", "there is a shortage of capital, and we need extra financing"),
        ("positive", "growth is strong and we have plenty of liquidity"),
        ("negative", "there are doubts about our finances"),
        ("neutral",  "profits are flat"),
    ]
    for expected, text in cases:
        r = a.analyze(text)
        marker = "OK" if r["sentiment_label"] == expected else "!!"
        print(
            f"[{marker}] expect={expected:<8} got={r['sentiment_label']:<8} "
            f"conf={r['confidence']:.2%}  pos={r['positive_score']:.2f} "
            f"neg={r['negative_score']:.2f} neu={r['neutral_score']:.2f}  "
            f"| {text}"
        )


if __name__ == "__main__":
    main()
