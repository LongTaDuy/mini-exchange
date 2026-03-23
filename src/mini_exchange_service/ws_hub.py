"""
Fan-out of market events to WebSocket clients. Runs broadcasts on the app event loop
even when the exchange is invoked from sync HTTP handlers (thread pool).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

from mini_exchange import OrderBook, Trade
from mini_exchange_service.ws_payloads import book_top_event, dumps_event, trade_event

logger = logging.getLogger(__name__)


class MarketEventHub:
    """
    Subscriptions: each WebSocket can listen to one or more symbols.
    Emits are scheduled with ``call_soon_threadsafe`` so sync route handlers can publish.
    """

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # symbol -> connected websockets interested in that symbol
        self._by_symbol: Dict[str, Set[WebSocket]] = {}
        # reverse index for cleanup on disconnect
        self._ws_symbols: Dict[WebSocket, Set[str]] = {}

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def _schedule_send(self, symbol: str, payload: str) -> None:
        loop = self._loop
        if loop is None:
            logger.debug("MarketEventHub: no event loop attached; dropping event")
            return

        def _run() -> None:
            loop.create_task(self._send_to_symbol(symbol, payload))

        try:
            loop.call_soon_threadsafe(_run)
        except RuntimeError:
            logger.exception("MarketEventHub: failed to schedule broadcast")

    def emit_trade(self, symbol: str, trade: Trade) -> None:
        payload = dumps_event(trade_event(symbol, trade))
        self._schedule_send(symbol, payload)

    def emit_book_top(self, symbol: str, book: OrderBook) -> None:
        payload = dumps_event(book_top_event(symbol, book))
        self._schedule_send(symbol, payload)

    async def _send_to_symbol(self, symbol: str, text: str) -> None:
        recipients = list(self._by_symbol.get(symbol, ()))
        for ws in recipients:
            try:
                await ws.send_text(text)
            except Exception:
                await self._forget(ws)

    async def _forget(self, ws: WebSocket) -> None:
        syms = self._ws_symbols.pop(ws, set())
        for sym in syms:
            bucket = self._by_symbol.get(sym)
            if bucket is not None:
                bucket.discard(ws)
                if not bucket:
                    del self._by_symbol[sym]

    def subscribe(self, ws: WebSocket, symbols: Set[str]) -> None:
        clean = {s.strip() for s in symbols if isinstance(s, str) and s.strip()}
        for sym in clean:
            self._by_symbol.setdefault(sym, set()).add(ws)
        self._ws_symbols.setdefault(ws, set()).update(clean)

    def unsubscribe(self, ws: WebSocket, symbols: Set[str]) -> None:
        for sym in symbols:
            bucket = self._by_symbol.get(sym)
            if bucket is not None:
                bucket.discard(ws)
                if not bucket:
                    del self._by_symbol[sym]
        tracked = self._ws_symbols.get(ws)
        if tracked is not None:
            tracked -= symbols
            if not tracked:
                self._ws_symbols.pop(ws, None)

    async def run_session(self, websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                try:
                    msg = await websocket.receive_json()
                except WebSocketDisconnect:
                    break
                await self._handle_client_message(websocket, msg)
        finally:
            await self._forget(websocket)

    async def _handle_client_message(
        self, websocket: WebSocket, msg: Dict[str, Any]
    ) -> None:
        action = msg.get("action")
        if action == "subscribe":
            raw = msg.get("symbols") or []
            if not isinstance(raw, list):
                await websocket.send_text(
                    dumps_event(
                        {"type": "error", "message": "symbols must be a list of strings"}
                    )
                )
                return
            syms = {str(x) for x in raw}
            self.subscribe(websocket, syms)
            await websocket.send_text(
                dumps_event({"type": "subscribed", "symbols": sorted(syms)})
            )
            for sym in sorted(syms):
                book = _book_for_symbol(websocket, sym)
                if book is not None:
                    await websocket.send_text(dumps_event(book_top_event(sym, book)))
        elif action == "unsubscribe":
            raw = msg.get("symbols") or []
            if not isinstance(raw, list):
                await websocket.send_text(
                    dumps_event(
                        {"type": "error", "message": "symbols must be a list of strings"}
                    )
                )
                return
            syms = {str(x) for x in raw}
            self.unsubscribe(websocket, syms)
            await websocket.send_text(
                dumps_event({"type": "unsubscribed", "symbols": sorted(syms)})
            )
        elif action == "ping":
            await websocket.send_text(dumps_event({"type": "pong"}))
        else:
            await websocket.send_text(
                dumps_event(
                    {
                        "type": "error",
                        "message": "unknown action; use subscribe, unsubscribe, or ping",
                    }
                )
            )


def _book_for_symbol(websocket: WebSocket, symbol: str) -> Optional[OrderBook]:
    exchange = getattr(websocket.app.state, "exchange", None)
    if exchange is None:
        return None
    try:
        return exchange.get_orderbook(symbol)
    except ValueError:
        return None
