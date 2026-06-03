"""HTTP routes for the matching service.

Each route maps directly onto an existing `Exchange` method. Domain failures
(`InvalidOrderError`, `ValueError`, bad decimals) become HTTP 400; missing
resting orders become HTTP 404. No matching logic lives here.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException

from mini_exchange import Exchange, InvalidOrderError
from mini_exchange.order import Order

from app.dependencies import get_exchange
from app.schemas import (
    CancelOrderRequest,
    CancelOrderResponse,
    OrderBookResponse,
    OrderLookupResponse,
    SubmitOrderRequest,
    SubmitOrderResponse,
)
from app.serializers import (
    serialize_order,
    serialize_order_book,
    serialize_trade,
    top_of_book,
)

router = APIRouter()


def _to_decimal(field: str, raw: str) -> Decimal:
    try:
        return Decimal(raw)
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail={"code": "bad_request", "message": f"{field} is not a valid number: {raw!r}"},
        )


@router.post("/orders", response_model=SubmitOrderResponse)
def submit_order(
    req: SubmitOrderRequest, exchange: Exchange = Depends(get_exchange)
) -> dict:
    price = _to_decimal("price", req.price)
    quantity = _to_decimal("quantity", req.quantity)

    try:
        order = Order(
            req.order_id,
            req.side,
            price,
            quantity,
            timestamp=req.timestamp,
        )
        trades, book = exchange.submit_order(req.symbol, order)
    except InvalidOrderError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_order", "message": str(exc)},
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "bad_request", "message": str(exc)},
        )

    resting = book.get_order(req.order_id) is not None
    return {
        "symbol": req.symbol,
        "order": {
            "order_id": req.order_id,
            "side": req.side.value,
            "price": str(price),
            "quantity_submitted": str(quantity),
            "quantity_remaining": str(order.quantity),
            "resting": resting,
            "timestamp": req.timestamp,
        },
        "trades": [serialize_trade(t) for t in trades],
        "book": top_of_book(book),
    }


@router.post("/orders/cancel", response_model=CancelOrderResponse)
def cancel_order(
    req: CancelOrderRequest, exchange: Exchange = Depends(get_exchange)
) -> dict:
    try:
        canceled = exchange.cancel_order(req.symbol, req.order_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "bad_request", "message": str(exc)},
        )

    book = exchange.get_orderbook(req.symbol)
    return {
        "symbol": req.symbol,
        "order_id": req.order_id,
        "canceled": canceled is not None,
        "canceled_quantity": None if canceled is None else str(canceled.quantity),
        "book": top_of_book(book),
    }


@router.get("/orderbook/{symbol}", response_model=OrderBookResponse)
def get_orderbook(
    symbol: str, exchange: Exchange = Depends(get_exchange)
) -> dict:
    try:
        book = exchange.get_orderbook(symbol)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "bad_request", "message": str(exc)},
        )
    return serialize_order_book(symbol, book)


@router.get("/orders/{order_id}", response_model=OrderLookupResponse)
def get_order(
    order_id: str, exchange: Exchange = Depends(get_exchange)
) -> dict:
    found = exchange.get_order_any(order_id)
    if found is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Resting order not found"},
        )
    symbol, order = found
    return {"symbol": symbol, "order": serialize_order(order)}
