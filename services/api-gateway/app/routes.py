"""Public gateway routes.

Thin pass-through layer: each route forwards to the matching service over HTTP
via `client.forward`. No domain/engine imports here by design.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body

from app.client import forward

router = APIRouter()


@router.post("/orders")
async def submit_order(payload: Dict[str, Any] = Body(...)) -> Any:
    return await forward("POST", "/orders", json=payload)


@router.post("/orders/cancel")
async def cancel_order(payload: Dict[str, Any] = Body(...)) -> Any:
    return await forward("POST", "/orders/cancel", json=payload)


@router.get("/orderbook/{symbol}")
async def get_orderbook(symbol: str) -> Any:
    return await forward("GET", f"/orderbook/{symbol}")


@router.get("/orders/{order_id}")
async def get_order(order_id: str) -> Any:
    return await forward("GET", f"/orders/{order_id}")
