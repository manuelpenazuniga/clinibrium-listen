"""Suite-wide test isolation."""
from __future__ import annotations

import os

import pytest

# `clinibrium.api` builds its module-level `app` on import, i.e. during
# collection, before any fixture runs (Codex impl r2): clear it up front too.
os.environ.pop("WEB_CONCURRENCY", None)


@pytest.fixture(autouse=True)
def _single_process_env(monkeypatch):
    """Plan T5: `create_app()` refuses to start the demo limiter when
    WEB_CONCURRENCY asks for more than one worker. A developer shell that
    exports it must not make unrelated tests fail."""
    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
