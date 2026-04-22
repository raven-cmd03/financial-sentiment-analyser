"""Shared test fixtures.

The tests in this suite deliberately avoid booting the full FastAPI app or a real
Postgres / Redis / Chroma stack. They exist to catch import-time regressions and
narrow logic bugs (the sort of thing that slipped through review in
workers/tasks.py and correlation._load_aligned_data).
"""

import os
import sys
from pathlib import Path

# Make sure the tests run against the backend package without requiring a full
# package install. Equivalent to running pytest with `cwd=backend/`.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Provide dummy required env values so pydantic-settings doesn't error during
# `Settings()` construction in unrelated imports (e.g. database module).
os.environ.setdefault("SECRET_KEY", "test-secret-not-a-placeholder")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SYNC_DATABASE_URL", "sqlite:///:memory:")
