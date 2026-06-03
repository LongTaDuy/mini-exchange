"""Service-wide dependencies.

Holds a single in-process `Exchange` instance (the matching service owns one
exchange for the life of the process) and exposes it as a FastAPI dependency.
"""

from __future__ import annotations

from functools import lru_cache

from mini_exchange import Exchange


@lru_cache(maxsize=1)
def _exchange_singleton() -> Exchange:
    return Exchange()


def get_exchange() -> Exchange:
    """FastAPI dependency returning the process-wide `Exchange` instance."""
    return _exchange_singleton()
