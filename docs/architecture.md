# Architecture

This document describes the runtime architecture of Mini Exchange after the
split from a single FastAPI app into a small microservice topology. The
matching engine itself is unchanged; it is reused as a shared library.

## Current microservice architecture

```text
Client
  -> API Gateway            (FastAPI, :8000)
      -> Matching Service   (FastAPI, :8001)
          -> mini_exchange core library
```

| Component | Role |
|-----------|------|
| **API Gateway** (`services/api-gateway`) | Public HTTP entrypoint. Forwards requests to the Matching Service over HTTP (`httpx`) and maps downstream/transport failures to clean responses. Owns no domain logic. |
| **Matching Service** (`services/matching-service`) | Owns a single in-process `Exchange`. Exposes REST for order submission, cancellation, order book snapshots, and resting-order lookup. |
| **Core library** (`src/mini_exchange`) | Matching engine, order book structures, multi-symbol routing, validation, and event logging. Imported by the Matching Service; never imported by the gateway. |

Services communicate **only over HTTP**. `Decimal` money fields are serialized
as **strings** end to end so precision survives the network hop.

## Request flow: submitting an order

```text
Client
  │  POST /orders  {symbol, order_id, side, price, quantity}
  ▼
API Gateway (:8000)
  │  validates JSON shape, forwards POST /orders via httpx
  ▼
Matching Service (:8001)
  │  parse price/quantity -> Decimal
  │  build Order, call Exchange.submit_order(symbol, order)
  ▼
mini_exchange core
  │  MatchingEngine matches against the opposite side (price-time priority),
  │  emits Trade(s), rests any remainder on the OrderBook
  ▼
Matching Service
  │  serialize {order, trades, top-of-book} with Decimals as strings
  ▼
API Gateway
  │  returns downstream JSON + status code verbatim
  ▼
Client
```

Errors: invalid input or domain failures return `400`; the gateway passes the
status and error body through unchanged.

## Request flow: canceling an order

```text
Client
  │  POST /orders/cancel  {symbol, order_id}
  ▼
API Gateway (:8000)
  │  forwards POST /orders/cancel via httpx
  ▼
Matching Service (:8001)
  │  Exchange.cancel_order(symbol, order_id)
  ▼
mini_exchange core
  │  OrderBook removes the resting order from its price level (no matching);
  │  empty levels are pruned
  ▼
Matching Service
  │  respond {canceled: bool, canceled_quantity, top-of-book}
  ▼
API Gateway -> Client
```

Canceling an unknown order is **not** an error: the response reports
`canceled: false` with a `200`.

## Why the matching engine remains a shared core library

The engine in `src/mini_exchange` is pure, framework-free Python with no HTTP,
serialization, or I/O concerns. Keeping it as a library rather than folding it
into a service yields several benefits:

- **Reusability** — it can be imported directly for tests, the `demo.py`
  walkthrough, the `benchmark.py` throughput check, or embedded in any future
  service without an HTTP dependency.
- **Testability** — matching correctness is verified against the library in
  isolation (FIFO, partial fills, multi-symbol), independent of transport.
- **Stable boundary** — services own edge concerns (routing, serialization,
  error mapping); the engine owns matching semantics. The split was achieved
  without modifying engine internals.
- **Optionality** — the core can later be promoted into a dedicated process,
  sharded per symbol, or driven by an event log, without rewriting its logic.

## Known limitations

- **In-memory state** — the `Exchange` lives in the Matching Service process;
  restarting the service loses the order book.
- **No persistence** — no write-ahead log, snapshots, or replay/recovery.
- **No authentication or authorization** — endpoints are open; no users, keys,
  or rate limits.
- **No distributed event bus** — there is no Kafka/Redis stream; trades and
  book updates are not published to external consumers.
- **No horizontal scaling for the Matching Service** — a single instance owns
  all symbols' books; running multiple replicas would split state. Scaling
  requires per-symbol sharding and a single-writer contract.

## Future improvements

- **market-data-service** — a dedicated service that subscribes to trade and
  top-of-book events and fans them out to clients (e.g. WebSocket feeds).
- **Redis/Kafka event bus** — publish `trade_executed` / book updates for
  decoupled consumers and durable streaming.
- **Persistence / WAL** — append-only command and trade log plus periodic
  snapshots, enabling recovery and deterministic replay.
- **Metrics & tracing** — per-service Prometheus metrics (latency histograms,
  queue depth) and OpenTelemetry traces across the gateway → matching hop.
- **Idempotency keys** — safe client retries on `POST /orders` without
  double-submission.
- **Auth & rate limits** — API keys / JWT and per-client throttling at the
  gateway edge.
