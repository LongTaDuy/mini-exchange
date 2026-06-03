# ADR 0001: Microservice boundaries

- **Status:** Accepted
- **Date:** 2026-06-03

## Context

Mini Exchange began as a single FastAPI application that imported the
`mini_exchange` matching engine directly and exposed it over HTTP. We wanted to
evolve it into a clean, microservice-oriented architecture suitable as a
backend portfolio project, while:

- preserving the existing matching engine logic and tests,
- avoiding heavy infrastructure (no database, Kafka, or Redis yet),
- keeping the code simple and readable.

The central question was **where to draw service boundaries** without
overengineering or duplicating the core domain logic.

## Decision

Split the system into two thin FastAPI services on top of the unchanged core
library:

- **API Gateway** (`:8000`) — the public entrypoint. It forwards requests to
  the Matching Service over HTTP (`httpx`) and maps downstream and transport
  errors to clean responses. It contains no domain logic and does not import
  the engine.
- **Matching Service** (`:8001`) — owns a single in-process `Exchange` and
  exposes REST for order submission, cancellation, order book snapshots, and
  resting-order lookup.
- **Core library** (`src/mini_exchange`) — remains a pure, framework-free
  package owning matching rules and order book structures, imported only by the
  Matching Service.

Services communicate over HTTP for v1. `Decimal` values cross all boundaries as
strings. The legacy `src/mini_exchange_service` is retained for now and not
removed as part of this change.

## Consequences

**Positive**

- Clear separation of edge concerns (routing, serialization, error mapping)
  from matching semantics.
- The matching engine stays reusable and independently testable; the split
  required no changes to engine internals.
- Service boundaries are explicit, creating natural seams for future services
  (market data, persistence) and cross-cutting concerns (auth, metrics).
- Local multi-service development is simple via `docker compose up --build`.

**Negative / trade-offs**

- An extra network hop adds latency and a new failure mode (the gateway must
  handle the Matching Service being unavailable → `503`/`504`).
- Matching Service state is in-memory and single-instance; it cannot be scaled
  horizontally without per-symbol sharding.
- Two services use the same `app` package name, which requires care when
  importing both in a single test process.

## Alternatives considered

- **Keep the monolith.** Simplest, but does not demonstrate service boundaries
  and offers no seam for future services. Rejected for the project's goals.
- **Gateway imports the engine directly (shared library, single process).**
  Lower latency, but erases the boundary the refactor is meant to showcase and
  couples the edge to the domain. Rejected.
- **Introduce a message bus (Kafka/Redis) immediately.** Enables streaming and
  decoupling, but is premature infrastructure for v1 and conflicts with the
  "avoid overengineering" constraint. Deferred to a future ADR.
- **Persist state now (database / WAL).** Valuable for durability, but not
  required to establish the service boundaries; deferred.
