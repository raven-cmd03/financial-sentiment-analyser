"""Backtest trader-agent simulation subsystem.

See backend/app/services/simulation/engine.py for the top-level entry
point ``run_simulation``. The subsystem is deliberately self-contained
so it can be driven from a Celery task, a CLI script, or a test with
no other platform code required.
"""

from app.services.simulation.profiles import (
    TRADER_PROFILES,
    VARIANTS,
    TraderProfile,
    get_profile,
)
from app.services.simulation.engine import run_simulation

__all__ = [
    "TRADER_PROFILES",
    "VARIANTS",
    "TraderProfile",
    "get_profile",
    "run_simulation",
]
