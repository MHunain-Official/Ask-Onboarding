"""Phase 7 security stretch helpers that complement `security.py`
(AGENTS.md §3.2, §5.8, §5.12): per-user rate limiting and a cheap,
log-only prompt-injection pattern flagger.

CSRF (`require_csrf_header`) and ACL (`allowed_access_levels`) already
live in `security.py` — this file only adds the two pieces that were
still missing, kept small and separate on purpose.
"""

import re
import time
import uuid
from collections import defaultdict
from functools import lru_cache
from threading import Lock

from fastapi import Depends, HTTPException, status

from app.config import Settings, get_settings
from app.models import User
from app.security import require_user

_WINDOW_SECONDS = 60.0


class RateLimiter:
    """A simple in-memory sliding-window counter per `(user_id, action)`.

    AGENTS.md §3.2 explicitly allows "simple in-DB or in-memory token
    bucket" for this — in-memory is enough for a single-process demo
    deployment and needs no migration. A multi-instance deployment would
    move this into Postgres (one row per user/action/window), the same
    way the rest of the app already avoids any other shared process state.
    """

    def __init__(self) -> None:
        self._hits: dict[tuple[uuid.UUID, str], list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, user_id: uuid.UUID, action: str, limit_per_minute: int) -> None:
        """Raise 429 if `user_id` has already made `limit_per_minute`
        `action` requests in the last 60 seconds; otherwise record this one."""
        key = (user_id, action)
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            cutoff = now - _WINDOW_SECONDS
            while hits and hits[0] < cutoff:
                hits.pop(0)
            if len(hits) >= limit_per_minute:
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    f"Too many {action} requests. Please wait a moment and try again.",
                )
            hits.append(now)

    def reset(self) -> None:
        """Test-only hook, mirrors `get_circuit_breaker.cache_clear()`."""
        with self._lock:
            self._hits.clear()


@lru_cache
def get_rate_limiter() -> RateLimiter:
    """Process-wide singleton, same pattern as `get_circuit_breaker`."""
    return RateLimiter()


def require_chat_rate_limit(
    user: User = Depends(require_user), settings: Settings = Depends(get_settings)
) -> None:
    get_rate_limiter().check(user.id, "chat", settings.rate_limit_chat_per_minute)


def require_upload_rate_limit(
    user: User = Depends(require_user), settings: Settings = Depends(get_settings)
) -> None:
    get_rate_limiter().check(user.id, "upload", settings.rate_limit_upload_per_minute)


# --- Prompt-injection pattern flagger (AGENTS.md §5.8) ---------------------
#
# This is deliberately cheap and never the actual defence: the real
# defences are the untrusted-data prompt rules, the tool that cannot write,
# ACL in SQL, and citation validation (§5.5, §3.2, §5.11). This regex only
# flags a suspicious question or document so an admin can review it later
# (`audit_events.event_type == "injection_pattern_flagged"`); it never
# blocks, rewrites, or refuses anything by itself.

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+|any\s+)?(previous|earlier|prior)\s+(rules|instructions)", re.I),
    re.compile(
        r"disregard\s+(all\s+|any\s+)?(previous|earlier|prior)\s+(rules|instructions)", re.I
    ),
    re.compile(r"system\s*(override|prompt)", re.I),
    re.compile(r"reveal\s+(your|the)\s+(system\s+prompt|hidden\s+rules|instructions)", re.I),
    re.compile(r"you\s+are\s+now\s+in\s+\w+\s+mode", re.I),
    re.compile(r"new\s+instructions\s*:", re.I),
    re.compile(r"print\s+(the\s+)?full\s+text\s+of\s+your", re.I),
]


def matches_injection_pattern(text: str) -> bool:
    """True if `text` contains a common prompt-injection phrase. Log only —
    never used to block a question or reject a document (§5.8)."""
    return any(pattern.search(text) for pattern in _INJECTION_PATTERNS)
