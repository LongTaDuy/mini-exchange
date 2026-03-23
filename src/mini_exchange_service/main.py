from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from mini_exchange import Exchange, InvalidOrderError
from mini_exchange.event_log import log_event
from mini_exchange_service.api import router
from mini_exchange_service.errors import json_error
from mini_exchange_service.notifying_exchange import NotifyingExchange
from mini_exchange_service.schemas import ErrorDetail
from mini_exchange_service.ws_api import router as ws_router
from mini_exchange_service.ws_hub import MarketEventHub


def create_app(exchange: Exchange | None = None) -> FastAPI:
    hub: MarketEventHub | None = None
    if exchange is None:
        hub = MarketEventHub()
        exchange = NotifyingExchange(hub)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if hub is not None:
            hub.attach_loop(asyncio.get_running_loop())
        yield

    app = FastAPI(
        title="Mini Exchange API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.exchange = exchange
    app.state.hub = hub
    app.include_router(router)
    if hub is not None:
        app.include_router(ws_router)

    @app.exception_handler(InvalidOrderError)
    def _invalid_order_handler(_, exc: InvalidOrderError):  # type: ignore[no-untyped-def]
        log_event(
            "validation_failure",
            source="http",
            reason=str(exc),
            detail="unhandled_invalid_order",
        )
        return json_error(
            400,
            code="invalid_order",
            message=str(exc),
        )

    @app.exception_handler(RequestValidationError)
    def _validation_handler(_, exc: RequestValidationError):  # type: ignore[no-untyped-def]
        errs = exc.errors()
        if errs:
            first = errs[0]
            loc = first.get("loc") or ()
            log_event(
                "validation_failure",
                source="http",
                path=".".join(str(x) for x in loc),
                reason=str(first.get("msg", "")),
                error_count=len(errs),
            )
        else:
            log_event("validation_failure", source="http", reason="request validation failed")
        details: list[ErrorDetail] = []
        for err in exc.errors():
            loc = err.get("loc") or ()
            path = ".".join(str(x) for x in loc)
            details.append(
                ErrorDetail(
                    path=path,
                    message=str(err.get("msg", "")),
                    code=str(err.get("type", "")) or None,
                )
            )
        return json_error(
            422,
            code="validation_error",
            message="Request validation failed",
            details=details,
        )

    return app


app = create_app()
