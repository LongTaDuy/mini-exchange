"""Gateway configuration sourced from the environment."""

from __future__ import annotations

import os

# Base URL of the matching service. Override via the MATCHING_SERVICE_URL env
# var (e.g. http://matching:8001 inside docker-compose).
MATCHING_SERVICE_URL: str = os.environ.get(
    "MATCHING_SERVICE_URL", "http://localhost:8001"
).rstrip("/")

# Upstream request timeout in seconds.
REQUEST_TIMEOUT_SECONDS: float = float(
    os.environ.get("MATCHING_SERVICE_TIMEOUT", "10")
)
