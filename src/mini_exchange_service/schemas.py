"""
API response contract (v2) — structured JSON for clients and frontends.

Suggested shape (success):
  {
    "success": true,
    "symbol": "BTC-USD",
    "order": {
      "order_id": "...",
      "side": "buy" | "sell",
      "price": "...",
      "quantity_submitted": "...",
      "quantity_remaining": "...",
      "resting": true | false,
      "timestamp": 0.0
    },
    "trades": [ { "trade_id", "price", "quantity", "buy_order_id", "sell_order_id" } ],
    "book": { "best_bid": "..." | null, "best_ask": "..." | null }
  }

Suggested shape (error):
  {
    "success": false,
    "error": {
      "code": "validation_error" | "invalid_order" | "bad_request" | "not_found" | ...,
      "message": "human-readable summary",
      "details": [ { "path": "body.field", "message": "...", "code": "optional" } ]
    }
  }

Decimals are serialized as strings in JSON for precision.
"""

from __future__ import annotations

from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from mini_exchange.order import Side


# --- Shared pieces -----------------------------------------------------------


class TopOfBook(BaseModel):
    """Best bid / ask after the operation (null if no resting liquidity on that side)."""

    best_bid: Optional[Decimal] = None
    best_ask: Optional[Decimal] = None


class TradeView(BaseModel):
    trade_id: str
    price: Decimal
    quantity: Decimal
    buy_order_id: str
    sell_order_id: str


class AcceptedOrderView(BaseModel):
    """The submitted order after matching (remaining qty + whether it rests)."""

    order_id: str
    side: Side
    price: Decimal
    quantity_submitted: Decimal
    quantity_remaining: Decimal
    resting: bool
    timestamp: float


class RestingOrderSummary(BaseModel):
    order_id: str
    quantity: Decimal


class OrderBookLevel(BaseModel):
    price: Decimal
    orders: List[RestingOrderSummary]


class FullBookView(BaseModel):
    best_bid: Optional[Decimal] = None
    best_ask: Optional[Decimal] = None
    bids: List[OrderBookLevel] = []
    asks: List[OrderBookLevel] = []


class RestingOrderDetail(BaseModel):
    order_id: str
    side: Side
    price: Decimal
    quantity: Decimal
    timestamp: float


# --- Errors (consistent across 4xx/422) -------------------------------------


class ErrorDetail(BaseModel):
    path: str = ""
    message: str
    code: Optional[str] = None


class ErrorBody(BaseModel):
    code: str
    message: str
    details: List[ErrorDetail] = []


class ApiErrorResponse(BaseModel):
    success: Literal[False] = False
    error: ErrorBody


# --- Requests ---------------------------------------------------------------


class PlaceOrderRequest(BaseModel):
    symbol: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    side: Side
    price: Decimal
    quantity: Decimal
    timestamp: float = 0.0


class CancelOrderRequest(BaseModel):
    symbol: str = Field(min_length=1)
    order_id: str = Field(min_length=1)


# --- Success responses -------------------------------------------------------


class PlaceOrderSuccess(BaseModel):
    success: Literal[True] = True
    symbol: str
    order: AcceptedOrderView
    trades: List[TradeView] = []
    book: TopOfBook


class CancelOrderSuccess(BaseModel):
    success: Literal[True] = True
    symbol: str
    order_id: str
    canceled: bool
    canceled_quantity: Optional[Decimal] = None
    book: TopOfBook


class OrderBookSuccess(BaseModel):
    success: Literal[True] = True
    symbol: str
    book: FullBookView


class GetOrderSuccess(BaseModel):
    success: Literal[True] = True
    symbol: str
    order: RestingOrderDetail
