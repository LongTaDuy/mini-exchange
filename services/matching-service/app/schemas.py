"""Pydantic request/response models for the matching service.

Price and quantity cross the API boundary as **strings** to avoid float
precision loss; the service converts them to `Decimal` internally and converts
back to strings on the way out (see `serializers.py`).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from mini_exchange.order import Side


# --- Requests ----------------------------------------------------------------


class SubmitOrderRequest(BaseModel):
    symbol: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    side: Side
    price: str = Field(min_length=1)
    quantity: str = Field(min_length=1)
    timestamp: float = 0.0


class CancelOrderRequest(BaseModel):
    symbol: str = Field(min_length=1)
    order_id: str = Field(min_length=1)


# --- Shared response pieces --------------------------------------------------


class TradeOut(BaseModel):
    trade_id: str
    price: str
    quantity: str
    buy_order_id: str
    sell_order_id: str


class TopOfBook(BaseModel):
    best_bid: Optional[str] = None
    best_ask: Optional[str] = None


class RestingOrderSummary(BaseModel):
    order_id: str
    quantity: str


class OrderBookLevel(BaseModel):
    price: str
    orders: List[RestingOrderSummary] = []


class AcceptedOrder(BaseModel):
    order_id: str
    side: Side
    price: str
    quantity_submitted: str
    quantity_remaining: str
    resting: bool
    timestamp: float


class RestingOrderDetail(BaseModel):
    order_id: str
    side: Side
    price: str
    quantity: str
    timestamp: float


# --- Responses ---------------------------------------------------------------


class SubmitOrderResponse(BaseModel):
    symbol: str
    order: AcceptedOrder
    trades: List[TradeOut] = []
    book: TopOfBook


class CancelOrderResponse(BaseModel):
    symbol: str
    order_id: str
    canceled: bool
    canceled_quantity: Optional[str] = None
    book: TopOfBook


class OrderBookResponse(BaseModel):
    symbol: str
    best_bid: Optional[str] = None
    best_ask: Optional[str] = None
    bids: List[OrderBookLevel] = []
    asks: List[OrderBookLevel] = []


class OrderLookupResponse(BaseModel):
    symbol: str
    order: RestingOrderDetail


class ErrorResponse(BaseModel):
    code: str
    message: str
