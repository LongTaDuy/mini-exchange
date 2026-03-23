#!/usr/bin/env python3
"""
Mini Exchange demo: multi-symbol exchange, fills, partial fills, and cancel.

Run from repo root:
  python demo.py
"""

from __future__ import annotations

from decimal import Decimal

from mini_exchange import Exchange, Order, Side, Trade


def _order(oid: str, side: Side, price: str, qty: str) -> Order:
    return Order(oid, side, Decimal(price), Decimal(qty), timestamp=0.0)


def _divider(title: str) -> None:
    line = "=" * 72
    print(f"\n{line}\n  {title}\n{line}")


def _print_trades(trades: list) -> None:
    if not trades:
        print("  Trades: (none)")
        return
    print("  Trades:")
    for t in trades:
        print(
            f"    {t.trade_id}  {t.quantity} @ {t.price}  "
            f"buy={t.buy_order_id}  sell={t.sell_order_id}"
        )


def _print_order_book(exchange: Exchange, symbol: str) -> None:
    book = exchange.get_orderbook(symbol)
    print(f"  Order book - {symbol}")
    print("    Asks (low -> high):")
    if not book.asks:
        print("      (empty)")
    else:
        for price, orders in book.asks.items():
            parts = [f"{o.order_id}:{o.quantity}" for o in orders]
            print(f"      {price}  [{' | '.join(parts)}]")
    print("    Bids (high -> low):")
    if not book.bids:
        print("      (empty)")
    else:
        for price, orders in book.bids.items():
            parts = [f"{o.order_id}:{o.quantity}" for o in orders]
            print(f"      {price}  [{' | '.join(parts)}]")


def _print_all_books(exchange: Exchange, symbols: tuple[str, ...]) -> None:
    _divider("Final order books")
    for sym in symbols:
        _print_order_book(exchange, sym)
        print()


def _step(
    n: int,
    label: str,
    exchange: Exchange,
    symbol: str,
    order: Order,
    *,
    trade_log: list[tuple[str, Trade]],
) -> None:
    orig_qty = order.quantity
    orig_price = order.price
    side = order.side.value
    oid = order.order_id
    trades, _ = exchange.submit_order(symbol, order)
    for t in trades:
        trade_log.append((symbol, t))
    print(f"\n  Step {n} - {label}")
    print(
        f"    Submit [{symbol}] {side.upper()} {orig_qty} @ {orig_price}  (id={oid})"
    )
    _print_trades(trades)
    rem = order.quantity
    if rem > 0:
        resting = exchange.get_order(symbol, oid) is not None
        print(f"    Remaining qty: {rem}  resting={'yes' if resting else 'no'}")


def _print_trade_recap(trade_log: list[tuple[str, Trade]]) -> None:
    _divider("All executed trades (in order)")
    if not trade_log:
        print("  (none)")
        return
    for sym, t in trade_log:
        print(
            f"    [{sym}]  {t.trade_id}  {t.quantity} @ {t.price}  "
            f"buy={t.buy_order_id}  sell={t.sell_order_id}"
        )


def main() -> None:
    ex = Exchange()
    symbols = ("BTC-USD", "ETH-USD")
    trade_log: list[tuple[str, Trade]] = []

    print("\n  Mini Exchange - live demo")
    print("  (BTC-USD: depth, partial/full fills, cancel | ETH-USD: isolated book)")

    # --- BTC-USD: liquidity at one price (FIFO), partial maker, sweep + resting bid ---
    _divider("BTC-USD - resting depth at $50,000")
    _step(
        1,
        "Rest sell 100 (Alice)",
        ex,
        "BTC-USD",
        _order("alice", Side.SELL, "50000", "100"),
        trade_log=trade_log,
    )
    _step(
        2,
        "Rest sell 50 (Bob) - same price, queued behind Alice (FIFO)",
        ex,
        "BTC-USD",
        _order("bob", Side.SELL, "50000", "50"),
        trade_log=trade_log,
    )
    _step(
        3,
        "Buy 100 - fully fills Alice (maker fully filled)",
        ex,
        "BTC-USD",
        _order("carol", Side.BUY, "50000", "100"),
        trade_log=trade_log,
    )
    _step(
        4,
        "Buy 30 - partial fill vs Bob; Bob keeps 20 on book",
        ex,
        "BTC-USD",
        _order("dave", Side.BUY, "50000", "30"),
        trade_log=trade_log,
    )
    _step(
        5,
        "Buy 25 - full fill vs Bob's 20; 5 rests as bid",
        ex,
        "BTC-USD",
        _order("erin", Side.BUY, "50000", "25"),
        trade_log=trade_log,
    )
    _step(
        6,
        "Sell at higher price - rests (no cross)",
        ex,
        "BTC-USD",
        _order("frank", Side.SELL, "51000", "10"),
        trade_log=trade_log,
    )

    _divider("BTC-USD - cancel resting order")
    _step(
        7,
        "Place bid to cancel next",
        ex,
        "BTC-USD",
        _order("ghost", Side.BUY, "49000", "5"),
        trade_log=trade_log,
    )
    canceled = ex.cancel_order("BTC-USD", "ghost")
    print("\n  Step 8 - Cancel order `ghost` on BTC-USD")
    if canceled:
        print(f"    Canceled: {canceled.order_id}  remaining qty removed: {canceled.quantity}")
    else:
        print("    (cancel failed - unexpected)")
    _print_order_book(ex, "BTC-USD")

    # --- ETH-USD: independent book; full fill on one trade ---
    _divider("ETH-USD - separate book (no cross with BTC)")
    _step(
        9,
        "Rest sell on ETH",
        ex,
        "ETH-USD",
        _order("eth-s1", Side.SELL, "3000", "5"),
        trade_log=trade_log,
    )
    _step(
        10,
        "Buy on ETH - partial fill vs eth-s1 (3 filled, 2 left on ask)",
        ex,
        "ETH-USD",
        _order("eth-b1", Side.BUY, "3000", "3"),
        trade_log=trade_log,
    )
    _step(
        11,
        "Buy on BTC only - does NOT touch ETH liquidity",
        ex,
        "BTC-USD",
        _order("btc-only", Side.BUY, "50000", "1"),
        trade_log=trade_log,
    )

    _print_trade_recap(trade_log)
    _print_all_books(ex, symbols)

    print("  Done.\n")


if __name__ == "__main__":
    main()
