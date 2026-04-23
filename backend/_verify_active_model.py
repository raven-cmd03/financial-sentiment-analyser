"""One-shot sanity check: make sure the newly-flagged fine-tune is
what the worker will actually load at inference time, and that it
produces differentiable predictions vs. the stock checkpoint.

Deletable after inspection.
"""
import hashlib
import json
from pathlib import Path

import torch

from app.config import get_settings
from app.database import SyncSessionLocal
from app.services.sentiment_analyzer import SentimentAnalyzer
from app.workers.tasks import _resolve_active_model_name


def _weight_fingerprint(model) -> str:
    """Stable checksum of the classifier head so we can compare the
    fine-tuned weights against the base model.
    """
    # The classification head is what fine-tuning actually changes the
    # most; hashing just it keeps this cheap and sensitive.
    head = model.classifier if hasattr(model, "classifier") else list(model.children())[-1]
    state = {k: v.detach().cpu().numpy().tobytes() for k, v in head.state_dict().items()}
    h = hashlib.md5()
    for k in sorted(state):
        h.update(k.encode())
        h.update(state[k])
    return h.hexdigest()[:12]


def main():
    settings = get_settings()
    session = SyncSessionLocal()
    try:
        active_path = _resolve_active_model_name(session)
    finally:
        session.close()

    print(f"Base (settings.FINBERT_MODEL):  {settings.FINBERT_MODEL}")
    print(f"Resolver active model:          {active_path}")
    print()

    if not active_path:
        print("No active fine-tune — worker would load the base model.")
        return

    # Check the files are actually there.
    p = Path(active_path)
    required = ["config.json", "model.safetensors"]
    for f in required:
        ok = (p / f).exists()
        print(f"  {f:25s} exists={ok}")
    print()

    # Load both and compare.
    print("Loading FINE-TUNED model...")
    ft = SentimentAnalyzer(model_name=active_path)
    ft_fp = _weight_fingerprint(ft.model)
    print(f"  fine-tuned classifier fingerprint: {ft_fp}")
    print(f"  device                           : {ft.device}")

    print()
    print("Loading BASE model for comparison...")
    base = SentimentAnalyzer(model_name=settings.FINBERT_MODEL)
    base_fp = _weight_fingerprint(base.model)
    print(f"  base classifier fingerprint      : {base_fp}")
    print()

    if ft_fp == base_fp:
        print("WARNING: fine-tuned and base classifier heads are IDENTICAL.")
        print("  Fine-tune did not differentiate — something is off.")
    else:
        print("OK: fine-tuned head differs from base head (expected).")

    # Label map comparisons.
    print()
    print("Label maps:")
    print(f"  base.id2label     : {base.model.config.id2label}")
    print(f"  fine-tune.id2label: {ft.model.config.id2label}")

    # Live inference on a few canonical sentences.
    tests = [
        "Apple beat earnings expectations and raised guidance.",
        "The company missed revenue estimates and slashed its outlook.",
        "Quarterly results were in line with expectations, no major changes.",
    ]
    print()
    print("Inference smoke test:")
    for t in tests:
        b = base.analyze(t)
        f = ft.analyze(t)
        print(f"  input: {t!r}")
        print(
            f"    base      : label={b['sentiment_label']:<9s} "
            f"pos={b['positive_score']:.3f} neg={b['negative_score']:.3f} "
            f"neu={b['neutral_score']:.3f}"
        )
        print(
            f"    fine-tune : label={f['sentiment_label']:<9s} "
            f"pos={f['positive_score']:.3f} neg={f['negative_score']:.3f} "
            f"neu={f['neutral_score']:.3f}"
        )


if __name__ == "__main__":
    main()
