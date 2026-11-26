"""In-memory rate limiting for auth endpoints (BUG-07).

Single-process limiter: per-key sliding window. Login is keyed by IP+email
(credential stuffing), signup by IP (spam). Returns 429 via the caller.
Multi-worker deployments should swap this for a shared store (Redis).
"""
import time
from collections import defaultdict

_WINDOWS: dict[str, list[float]] = defaultdict(list)


def _prune(key: str, window_seconds: float, now: float) -> list[float]:
    hits = [t for t in _WINDOWS.get(key, []) if now - t < window_seconds]
    _WINDOWS[key] = hits
    return hits


def check_rate_limit(key: str, limit: int, window_seconds: float) -> float:
    """Record an attempt; return 0 if allowed, else seconds to wait."""
    now = time.monotonic()
    hits = _prune(key, window_seconds, now)
    if len(hits) >= limit:
        return max(1.0, window_seconds - (now - hits[0]))
    hits.append(now)
    _WINDOWS[key] = hits
    return 0.0


def reset_rate_limit(key: str) -> None:
    _WINDOWS.pop(key, None)
