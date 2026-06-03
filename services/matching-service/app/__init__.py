"""Mini Exchange Matching Service (FastAPI).

Thin HTTP service that owns order submission, cancellation, order book
snapshots, and resting-order lookup. All matching logic is delegated to the
shared `mini_exchange` core library; no engine logic is duplicated here.
"""
