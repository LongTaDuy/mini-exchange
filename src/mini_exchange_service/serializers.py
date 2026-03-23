from __future__ import annotations

from decimal import Decimal
from typing import List

from mini_exchange import OrderBook, Order, Trade
from mini_exchange.order import Side
from mini_exchange_service.schemas import (
    AcceptedOrderView,
    CancelOrderSuccess,
    FullBookView,
    GetOrderSuccess,
    OrderBookLevel,
    OrderBookSuccess,
    PlaceOrderSuccess,
    RestingOrderDetail,
    RestingOrderSummary,
    TopOfBook,
    TradeView,
)


def trade_to_view(trade: Trade) -> TradeView:
    return TradeView(
        trade_id=trade.trade_id,
        price=trade.price,
        quantity=trade.quantity,
        buy_order_id=trade.buy_order_id,
        sell_order_id=trade.sell_order_id,
    )


def top_of_book(book: OrderBook) -> TopOfBook:
    return TopOfBook(
        best_bid=book.best_bid_price(),
        best_ask=book.best_ask_price(),
    )


def full_book_view(book: OrderBook) -> FullBookView:
    bids: List[OrderBookLevel] = []
    for price, orders in book.bids.items():
        bids.append(
            OrderBookLevel(
                price=price,
                orders=[
                    RestingOrderSummary(order_id=o.order_id, quantity=o.quantity)
                    for o in orders
                ],
            )
        )

    asks: List[OrderBookLevel] = []
    for price, orders in book.asks.items():
        asks.append(
            OrderBookLevel(
                price=price,
                orders=[
                    RestingOrderSummary(order_id=o.order_id, quantity=o.quantity)
                    for o in orders
                ],
            )
        )

    return FullBookView(
        best_bid=book.best_bid_price(),
        best_ask=book.best_ask_price(),
        bids=bids,
        asks=asks,
    )


def orderbook_success(symbol: str, book: OrderBook) -> OrderBookSuccess:
    return OrderBookSuccess(symbol=symbol, book=full_book_view(book))


def resting_order_detail(symbol: str, order: Order) -> GetOrderSuccess:
    return GetOrderSuccess(
        symbol=symbol,
        order=RestingOrderDetail(
            order_id=order.order_id,
            side=order.side,
            price=order.price,
            quantity=order.quantity,
            timestamp=order.timestamp,
        ),
    )


def place_order_success(
    symbol: str,
    *,
    order_id: str,
    side: Side,
    price: Decimal,
    quantity_submitted: Decimal,
    quantity_remaining: Decimal,
    resting: bool,
    timestamp: float,
    trades: List[Trade],
    book: OrderBook,
) -> PlaceOrderSuccess:
    return PlaceOrderSuccess(
        symbol=symbol,
        order=AcceptedOrderView(
            order_id=order_id,
            side=side,
            price=price,
            quantity_submitted=quantity_submitted,
            quantity_remaining=quantity_remaining,
            resting=resting,
            timestamp=timestamp,
        ),
        trades=[trade_to_view(t) for t in trades],
        book=top_of_book(book),
    )


def cancel_order_success(
    symbol: str,
    order_id: str,
    *,
    canceled: bool,
    canceled_quantity: Decimal | None,
    book: OrderBook,
) -> CancelOrderSuccess:
    return CancelOrderSuccess(
        symbol=symbol,
        order_id=order_id,
        canceled=canceled,
        canceled_quantity=canceled_quantity,
        book=top_of_book(book),
    )
