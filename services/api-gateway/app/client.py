"""HTTP client helpers for talking to the matching service.

A single shared `httpx.AsyncClient` is reused across requests (created on app
startup, closed on shutdown). Transport failures (timeout / connection) become
504 / 503; downstream 4xx/5xx responses are re-raised with their original
status code and body so clients see consistent errors.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx
from fastapi import HTTPException

from app.config import MATCHING_SERVICE_URL, REQUEST_TIMEOUT_SECONDS

_client: Optional[httpx.AsyncClient] = None


def get_client() -> httpx.AsyncClient:
    """Return the shared AsyncClient, creating it on first use."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=MATCHING_SERVICE_URL,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    return _client


async def close_client() -> None:
    """Close the shared client (call on application shutdown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _decode_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {"detail": response.text}


def _raise_for_downstream(response: httpx.Response) -> None:
    """Re-raise downstream errors, preserving status code and error body."""
    if response.status_code < 400:
        return
    body = _decode_body(response)
    detail = body.get("detail", body) if isinstance(body, dict) else body
    raise HTTPException(status_code=response.status_code, detail=detail)


async def forward(
    method: str,
    path: str,
    *,
    json: Optional[Any] = None,
    params: Optional[dict] = None,
) -> Any:
    """Forward a request to the matching service and return its JSON body.

    Raises HTTPException(504) on timeout, 503 on connection failure, and
    re-raises the downstream status code/body for 4xx/5xx responses.
    """
    client = get_client()
    try:
        response = await client.request(method, path, json=json, params=params)
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail={"code": "upstream_timeout", "message": "Matching service timed out"},
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "upstream_unavailable",
                "message": f"Matching service unavailable: {exc}",
            },
        )

    _raise_for_downstream(response)
    return _decode_body(response)
