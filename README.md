# Mini Exchange

A **limit-order matching engine** and small **HTTP API** in Python, built to read like production exchange infrastructure in miniature: correct price–time priority, partial fills, per-symbol order books, and explicit validation and observability.

---

## Project overview

Mini Exchange implements the **core of a spot-style order book**: clients submit **limit buy and sell orders**; the system **matches** them when prices cross, **updates resting liquidity**, and records **trades**. It is **not** a full trading venue (no custody, settlement, fees, or market data feeds)—it is a **focused backend sample** that shows how matching logic, book state, and an API can be separated cleanly.

**Stack:** Python 3.10+, `Decimal` for money-like fields, `unittest` for tests, optional **FastAPI** service for HTTP access.

---

## Why this project is interesting

- **Real domain complexity, small surface area.** Matching engines sit at the heart of exchanges; this repo shows **price–time priority**, **partial fills**, and **book consistency** without the noise of a full trading stack.
- **Clear separation of concerns.** `OrderBook` holds structure; `MatchingEngine` owns crossing logic; `Exchange` routes **multi-symbol** traffic; validation and errors stay **explicit**; the API layer maps HTTP to the core without embedding matching rules in routes.
- **Engineering hygiene.** **Invariant checks** on the book (debug builds), **structured JSON logging** for operations and failures, **42 tests** (FIFO, multi-symbol isolation, cancel flows, API smoke, WebSocket smoke), and a **walkthrough demo** for reviewers who prefer running code to reading slides.

For a recruiter or hiring manager, this reads as: *understands fin-tech primitives, can structure a service, tests meaningfully, and documents assumptions.*

---

## Architecture overview

```text
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  FastAPI    │────▶│   Exchange   │────▶│ MatchingEngine  │
│  (optional) │     │ (per symbol) │     │  + OrderBook    │
└─────────────┘     └──────────────┘     └─────────────────┘
```

| Layer | Responsibility |
|--------|----------------|
| **`Order` / `Trade`** | Immutable-style trade records; orders carry remaining quantity after fills. |
| **`OrderBook`** | Resting bids and asks: `dict[price] →` FIFO **linked list** of orders (plus `order_id → node` for O(1) cancel), heaps for **best bid/ask** with lazy cleanup of stale heap entries and a **best-price cache** synced from level keys. |
| **`MatchingEngine`** | Validates input, matches incoming orders against the opposite side, emits `Trade`s, rests remainder; optional **`symbol`** kwarg for logging only. |
| **`Exchange`** | One `MatchingEngine` (and thus one `OrderBook`) **per symbol**; routes `submit_order` / `cancel_order`; global order lookup by id across symbols. |
| **`validation` / `errors`** | Centralized rules; `InvalidOrderError` for domain failures. |
| **`event_log`** | Structured **JSON lines** (`order_received`, `trade_executed`, `order_canceled`, `validation_failure`) on logger `mini_exchange`. |
| **`mini_exchange_service`** | FastAPI app: Pydantic schemas, consistent **success/error JSON**, REST for orders / cancel / order book / order lookup, optional **`/ws`** market stream when using the default `NotifyingExchange` (see below). |

---

## Microservice Architecture

The project has been split from a single FastAPI app into a small, explicit
**microservice topology**. The matching logic is unchanged — it is reused as a
shared library — and two thin HTTP services are layered on top.

### The core package remains

`src/mini_exchange` is **untouched** and still owns all domain logic:

- the **matching engine** (price–time priority, partial fills),
- the **order book** structures (FIFO price levels, best bid/ask),
- **exchange routing** (one book per symbol, cross-symbol lookup),
- validation, errors, and structured event logging.

Both new services import this package; **no engine logic is duplicated**.

### New services

| Service | Port | Location |
|---------|------|----------|
| **API Gateway** | `8000` | `services/api-gateway/` |
| **Matching Service** | `8001` | `services/matching-service/` |

### Architecture diagram

```text
Client
  -> API Gateway            (FastAPI, :8000 — public routes, forwards over HTTP)
      -> Matching Service   (FastAPI, :8001 — owns the exchange)
          -> mini_exchange core library   (matching engine + order book)
```

The gateway talks to the matching service **only over HTTP** (via `httpx`);
it never imports the engine. Decimal money fields are serialized as **strings**
end to end, so precision is preserved across the network hop.

### Service responsibilities

| Component | Responsibilities |
|-----------|------------------|
| **API Gateway** | Public-facing API; forwards requests to the matching service; maps downstream/transport failures to clean HTTP errors (`400`/`404` passthrough, `503` upstream down, `504` timeout); simple `/health`. |
| **Matching Service** | Order submission, cancellation, order book snapshots, resting-order lookup; owns a single in-process `Exchange`; `/health`. |
| **Core Library (`mini_exchange`)** | Price–time priority, matching rules, partial fills, order book data structures, multi-symbol routing, validation. |

### Run locally without Docker

Install the core package once (this also provides FastAPI, Uvicorn, and HTTPX):

```bash
python -m pip install -e .
```

Start each service in its own terminal (run from inside the service directory so
`app.main:app` resolves):

```bash
# Terminal 1 — Matching Service (:8001)
cd services/matching-service
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# Terminal 2 — API Gateway (:8000)
cd services/api-gateway
# point the gateway at the matching service (default is http://localhost:8001)
# PowerShell:  $env:MATCHING_SERVICE_URL="http://localhost:8001"
# bash:        export MATCHING_SERVICE_URL=http://localhost:8001
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Swagger UI: gateway at [http://localhost:8000/docs](http://localhost:8000/docs),
matching service at [http://localhost:8001/docs](http://localhost:8001/docs).

### Run with Docker Compose

From the repository root:

```bash
docker compose up --build
```

This builds and starts both services on a shared network; the gateway is
configured with `MATCHING_SERVICE_URL=http://matching-service:8001`. Stop with
`docker compose down`.

### Example requests

```bash
# Health — gateway
curl http://localhost:8000/health

# Health — matching service (direct)
curl http://localhost:8001/health

# Submit a resting buy order (through the gateway)
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTC-USD","order_id":"b1","side":"buy","price":"100","quantity":"5"}'

# Submit a crossing sell order — produces a trade
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTC-USD","order_id":"s1","side":"sell","price":"100","quantity":"3"}'

# Get the order book snapshot
curl http://localhost:8000/orderbook/BTC-USD
```

### Why this architecture?

Splitting the gateway from the matching service **separates public API routing
from matching logic**, which keeps the **matching engine reusable** as a plain
library (importable, testable, and embeddable without HTTP). It makes
**service boundaries explicit** — the gateway owns edge concerns, the matching
service owns book state — and it **prepares the project for growth**: a future
market-data/streaming service, persistence (WAL + snapshots), authentication and
rate limiting at the gateway, and metrics/tracing per service can each be added
without disturbing the core engine.

---

## Matching rules

1. **Buys** consume the **lowest resting ask** first; **sells** consume the **highest resting bid** first.
2. **Price–time priority:** at the same price, orders are matched **FIFO** (queue order at each level).
3. **Trade size:** `min(aggressor_remaining, maker_remaining)` per execution; multiple trades per aggressive order when sweeping levels.
4. **Execution price:** resting (**maker**) price.
5. **Non-crossing** remainder is **rested** on the correct side; empty price levels are removed.
6. **Cancellation** removes a resting order from its level (no matching during cancel).

---

## Supported features

| Feature | Notes |
|---------|--------|
| Limit orders | Buy/sell, `Decimal` price and quantity |
| Partial & full fills | Makers and aggressors |
| Multi-symbol | e.g. `BTC-USD`, `ETH-USD`; **no cross-symbol matching** |
| Cancel | By `symbol` + `order_id` |
| Order lookup | By id on a book; `Exchange` can resolve across symbols |
| Validation | Non-positive qty/price, NaN/infinity, empty id, duplicate resting id |
| Debug invariants | Book not crossed, sorted bid/ask keys, positive quantities, index sync (`__debug__`; skipped with `python -O`) |
| HTTP API | Place order, cancel, order book snapshot, get resting order |
| WebSocket (`/ws`) | Real-time **trade** and **top-of-book** events per symbol (service layer only; enabled when `create_app()` uses the default `NotifyingExchange`) |
| Structured logging | JSON one-liner events for debugging and pipelines |

**Out of scope (v1):** market orders, GTC/IOC/FOK, fees, multiple users/auth, persistence/WAL, full order-book depth over WebSocket, self-trade prevention, tick sizes.

---

## Folder structure

```text
mini-exchange/
├── LICENSE
├── README.md
├── benchmark.py
├── demo.py
├── docker-compose.yml           # Gateway + Matching Service (local multi-service)
├── pyproject.toml
├── services/                    # Microservices (thin HTTP layers over the core)
│   ├── api-gateway/             # Public API, forwards to matching over HTTP (:8000)
│   │   ├── app/                 # main.py, routes.py, client.py, config.py
│   │   └── Dockerfile
│   └── matching-service/        # Owns the Exchange; REST for orders/book (:8001)
│       ├── app/                 # main.py, api.py, schemas.py, serializers.py, dependencies.py
│       └── Dockerfile
├── src/
│   ├── mini_exchange/           # Core engine
│   │   ├── __init__.py
│   │   ├── errors.py
│   │   ├── event_log.py
│   │   ├── exchange.py
│   │   ├── matching_engine.py
│   │   ├── order.py
│   │   ├── order_book.py
│   │   ├── trade.py
│   │   └── validation.py
│   └── mini_exchange_service/   # FastAPI layer
│       ├── __init__.py
│       ├── main.py
│       ├── api.py
│       ├── notifying_exchange.py
│       ├── schemas.py
│       ├── serializers.py
│       ├── errors.py
│       ├── ws_api.py
│       ├── ws_hub.py
│       └── ws_payloads.py
└── tests/
    ├── fixtures.py
    ├── test_api_gateway.py
    ├── test_matching_service.py
    ├── test_api_smoke.py
    ├── test_cancel.py
    ├── test_cancel_lifecycle.py
    ├── test_edge_cases.py
    ├── test_invalid_inputs.py
    ├── test_matching_fifo_and_depth.py
    ├── test_matching_scenarios.py
    ├── test_multi_symbol.py
    ├── test_order_lookup.py
    └── test_ws_stream.py
```

---

## Install

From the repository root:

```bash
python -m pip install -e .
```

This installs the **core package** and **API dependencies** (FastAPI, Uvicorn, HTTPX for tests). Requires **Python 3.10+**.

---

## Run tests

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Shared helpers: `tests/fixtures.py` (`limit_order`, test path setup). The suite covers matching edge cases, FIFO depth, multi-symbol isolation, cancel/re-place, invalid inputs, REST smoke tests, and WebSocket smoke (default app with `NotifyingExchange`).

---

## Run the demo

End-to-end script using **`Exchange`**: multi-symbol flow, full and partial fills, one cancellation, and final book snapshots.

```bash
python demo.py
```

Requires the package import path (e.g. `pip install -e .` from the repo root, or `PYTHONPATH=src`).

---

## Benchmark (optional)

Throughput smoke test for `MatchingEngine.submit_order` (synthetic random orders, fixed seed):

```bash
python benchmark.py
```

---

## Run the HTTP API

```bash
uvicorn mini_exchange_service.main:app --reload --port 8000
```

Open **Swagger UI** at [http://localhost:8000/docs](http://localhost:8000/docs).

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/orders` | Submit a limit order |
| `POST` | `/orders/cancel` | Cancel a resting order |
| `GET` | `/orderbook/{symbol}` | Bids, asks, and best bid/ask |
| `GET` | `/orders/{order_id}` | Resting order (searches symbols) |

Responses use a consistent envelope: **`success`**, nested **`order` / `trades` / `book`**, and structured **`error`** objects for 4xx/422. Decimal values are serialized as **strings** in JSON.

### WebSocket market stream (`/ws`)

Available when the app is created with **`create_app()`** (no arguments), which wires a **`NotifyingExchange`** and **`MarketEventHub`**. If you pass a plain **`Exchange()`** into `create_app`, `/ws` is not registered.

After connecting, send JSON commands:

- **Subscribe:** `{"action": "subscribe", "symbols": ["BTC-USD"]}` — you receive `subscribed`, a **`book_top`** snapshot per symbol, then **`trade`** / **`book_top`** as the REST API mutates the book.
- **Unsubscribe:** `{"action": "unsubscribe", "symbols": ["BTC-USD"]}`
- **Ping:** `{"action": "ping"}` → `{"type": "pong"}`

Event shapes are JSON objects with `"type": "trade"` or `"book_top"` (see `mini_exchange_service/ws_payloads.py`).

---

## Structured logging

Logger name: **`mini_exchange`**. Each line is a JSON object with an **`event`** field (`order_received`, `trade_executed`, `order_canceled`, `validation_failure`). Set level to **INFO** to see events (default root level is often WARNING):

```python
import logging
logging.getLogger("mini_exchange").setLevel(logging.INFO)
```

---

## Usage (library)

```python
from decimal import Decimal
from mini_exchange import Exchange, Order, Side

ex = Exchange()
ex.submit_order("BTC-USD", Order("s1", Side.SELL, Decimal("100"), Decimal("5")))
trades, book = ex.submit_order("BTC-USD", Order("b1", Side.BUY, Decimal("100"), Decimal("3")))
```

For a **single** instrument without symbols, use `MatchingEngine` directly (see `mini_exchange.matching_engine`).

---

## Possible future improvements

- **Durability:** append-only command/trade log, snapshots, replay for recovery.
- **Concurrency:** single-writer queue per symbol (or shard) with a defined serialisation contract.
- **Product features:** market orders, post-only, min notional, tick/lot size, self-trade prevention.
- **API:** auth, rate limits, idempotency keys, richer WebSocket feeds (full depth, replay).
- **Observability:** OpenTelemetry, metrics (latency histograms, queue depth).
- **Hardening:** property-based tests, fuzzing, formal invariants documented as ADRs.

---

## License

This project is licensed under the **MIT License** — see [`LICENSE`](LICENSE).
