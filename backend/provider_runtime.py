"""Provider runtime profile helpers."""

import os


def allow_private_providers() -> bool:
    return os.getenv("NAPICS_ALLOW_PRIVATE_PROVIDERS", "").strip().lower() in {"1", "true", "yes"}
