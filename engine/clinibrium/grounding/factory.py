"""`get_grounding()` — inline-only factory (Clinibrium Listen port).

Port note (SPECS §4): the original factory probed `DATABASE_URL` and could
return a `PgvectorGrounding`. The Listen port ships INLINE GROUNDING ONLY: the
pgvector backend (and its `asyncpg`/`pgvector` dependencies) is not ported, so
this factory always returns `InlineGrounding`. The original evaluation path
(AD-28, plan T1) already used the inline corpus exclusively, so no clinical
behaviour changes. The inline corpus itself (`inline.py`) is byte-identical to
the source and is pinned by the `grounding` fingerprint in
`versions_manifest.json`.
"""
from __future__ import annotations

from clinibrium.grounding.base import Grounding
from clinibrium.grounding.inline import InlineGrounding


def get_grounding() -> Grounding:
    """Returns the active `Grounding` implementation: always `InlineGrounding`.

    Never raises; safe to call at import time of downstream modules.
    """
    return InlineGrounding()
