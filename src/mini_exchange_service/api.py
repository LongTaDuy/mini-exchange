from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from mini_exchange import Exchange, InvalidOrderError
from mini_exchange.order import Order
from mini_exchange_service.errors import json_error
from mini_exchange_service.schemas import (
    CancelOrderRequest,
    CancelOrderSuccess,
    GetOrderSuccess,
    OrderBookSuccess,
    PlaceOrderRequest,
    PlaceOrderSuccess,
)
from mini_exchange_service.serializers import (
    cancel_order_success,
    orderbook_success,
    place_order_success,
    resting_order_detail,
)

router = APIRouter()


def get_exchange(request: Request) -> Exchange:
    return request.app.state.exchange


@router.post("/orders", response_model=PlaceOrderSuccess)
def post_order(req: PlaceOrderRequest, exchange: Exchange = Depends(get_exchange)):
    quantity_submitted = req.quantity
    try:
        order = Order(
            req.order_id,
            req.side,
            req.price,
            req.quantity,
            timestamp=req.timestamp,
        )
        trades, book = exchange.submit_order(req.symbol, order)
    except InvalidOrderError as e:
        return json_error(
            400,
            code="invalid_order",
            message=str(e),
        )
    except ValueError as e:
        return json_error(
            400,
            code="bad_request",
            message=str(e),
        )

    resting = book.get_order(req.order_id) is not None
    return place_order_success(
        req.symbol,
        order_id=req.order_id,
        side=req.side,
        price=req.price,
        quantity_submitted=quantity_submitted,
        quantity_remaining=order.quantity,
        resting=resting,
        timestamp=req.timestamp,
        trades=trades,
        book=book,
    )


@router.post("/orders/cancel", response_model=CancelOrderSuccess)
def cancel_order(
    req: CancelOrderRequest, exchange: Exchange = Depends(get_exchange)
):
    try:
        canceled = exchange.cancel_order(req.symbol, req.order_id)
    except ValueError as e:
        return json_error(
            400,
            code="bad_request",
            message=str(e),
        )

    book = exchange.get_orderbook(req.symbol)
    if canceled is None:
        return cancel_order_success(
            req.symbol,
            req.order_id,
            canceled=False,
            canceled_quantity=None,
            book=book,
        )

    return cancel_order_success(
        req.symbol,
        req.order_id,
        canceled=True,
        canceled_quantity=canceled.quantity,
        book=book,
    )


@router.get("/orderbook/{symbol}", response_model=OrderBookSuccess)
def get_orderbook(symbol: str, exchange: Exchange = Depends(get_exchange)):
    book = exchange.get_orderbook(symbol)
    return orderbook_success(symbol=symbol, book=book)


@router.get("/orders/{order_id}", response_model=GetOrderSuccess)
def get_order(order_id: str, exchange: Exchange = Depends(get_exchange)):
    found = exchange.get_order_any(order_id)
    if found is None:
        return json_error(
            404,
            code="not_found",
            message="Resting order not found",
        )
    sym, order = found
    return resting_order_detail(sym, order)
