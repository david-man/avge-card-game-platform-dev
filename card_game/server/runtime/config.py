from __future__ import annotations

import os


def resolve_init_finalize_timeout_seconds(
    env_name: str = 'INIT_FINALIZE_TIMEOUT_SECONDS',
    default_seconds: float = 8.0,
) -> float:
    raw = os.getenv(env_name, str(default_seconds)).strip()
    try:
        parsed = float(raw)
    except Exception:
        return default_seconds
    return max(1.0, min(parsed, 60.0))


def env_csv(name: str) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return []
    return [part.strip() for part in raw.split(',') if part.strip()]
