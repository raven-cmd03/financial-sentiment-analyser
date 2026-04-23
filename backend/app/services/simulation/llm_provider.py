"""Provider-agnostic LLM factory for the simulation subsystem.

The rest of the backend (RAG chat, etc) always uses Groq. Only the
simulation's trader agents + end-of-run narrative go through this
factory so we can swap between providers without touching the chat
stack. Controlled by ``settings.SIMULATION_LLM_PROVIDER``:

- ``"groq"``       → ``ChatGroq(model=GROQ_MODEL, api_key=GROQ_API_KEY)``
- ``"fireworks"``  → ``ChatFireworks(model=FIREWORKS_MODEL, api_key=FIREWORKS_API_KEY)``

Adding a provider is localised to this module. Everything downstream
just consumes ``with_structured_output`` / ``invoke``, which every
supported langchain chat model implements identically.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


def get_simulation_llm(temperature: float = 0.2, streaming: bool = False) -> Any:
    """Return a langchain chat model for the simulation, per settings.

    Raises ``RuntimeError`` with a clear message if the required API key
    for the selected provider is missing, rather than letting the first
    LLM call fail with a cryptic auth error half-way into a run.
    """
    settings = get_settings()
    provider = (settings.SIMULATION_LLM_PROVIDER or "groq").lower().strip()
    timeout = float(settings.SIMULATION_LLM_TIMEOUT_SEC)
    max_retries = int(settings.SIMULATION_LLM_MAX_RETRIES)

    if provider == "groq":
        from langchain_groq import ChatGroq

        if not settings.GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is not configured. Either set it in .env or "
                "switch SIMULATION_LLM_PROVIDER to a provider whose key is set."
            )
        # ChatGroq exposes ``timeout`` + ``max_retries`` with the same
        # semantics as the openai client it wraps.
        return ChatGroq(
            model=settings.GROQ_MODEL,
            api_key=settings.GROQ_API_KEY,
            temperature=temperature,
            streaming=streaming,
            timeout=timeout,
            max_retries=max_retries,
        )

    if provider == "fireworks":
        try:
            from langchain_fireworks import ChatFireworks
        except ImportError as exc:  # pragma: no cover - import-time guard
            raise RuntimeError(
                "SIMULATION_LLM_PROVIDER=fireworks but langchain-fireworks "
                "is not installed. Add it to requirements.txt and rebuild."
            ) from exc

        if not settings.FIREWORKS_API_KEY:
            raise RuntimeError(
                "FIREWORKS_API_KEY is not configured; set it in .env or "
                "switch SIMULATION_LLM_PROVIDER back to 'groq'."
            )
        # ChatFireworks uses ``request_timeout`` (float seconds) and
        # ``max_retries``. Without these, a single hung call blocks the
        # entire backtest — we saw this in production runs.
        return ChatFireworks(
            model=settings.FIREWORKS_MODEL,
            api_key=settings.FIREWORKS_API_KEY,
            temperature=temperature,
            streaming=streaming,
            request_timeout=timeout,
            max_retries=max_retries,
        )

    raise RuntimeError(
        f"Unknown SIMULATION_LLM_PROVIDER={provider!r}. "
        f"Expected 'groq' or 'fireworks'."
    )


def describe_provider() -> str:
    """Short string for logs / report headers, e.g. 'fireworks: <model>'."""
    settings = get_settings()
    provider = (settings.SIMULATION_LLM_PROVIDER or "groq").lower().strip()
    if provider == "fireworks":
        return f"fireworks: {settings.FIREWORKS_MODEL}"
    return f"groq: {settings.GROQ_MODEL}"


def get_structured_method() -> str | None:
    """Return the ``with_structured_output(method=...)`` value for the
    current provider.

    - Groq: ``None`` (use langchain's default = function_calling, which
      Groq's Llama 3.3 reliably honours).
    - Fireworks: ``"json_schema"``. The default function-calling path
      empirically returns ``None`` for Llama 3.3 70B on Fireworks
      (the model ignores the tool and replies with prose). json_schema
      is the documented reliable path on Fireworks' Llama instruct models.
    """
    settings = get_settings()
    provider = (settings.SIMULATION_LLM_PROVIDER or "groq").lower().strip()
    if provider == "fireworks":
        return "json_schema"
    return None
