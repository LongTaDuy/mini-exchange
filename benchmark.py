#!/usr/bin/env python3
"""
Mini Exchange — simple throughput benchmark.

What it measures
----------------
For N synthetic limit orders, records wall-clock time to run ``MatchingEngine.submit_order``
on each order (in-process Python only). Prints elapsed seconds and throughput in orders/sec.

Reproducibility
---------------
Uses ``random.seed`` (default 42). Order ids are deterministic ``id00000000``, ``id00000001``, …

How to run
----------
From the repo root, with the package on ``PYTHONPATH`` or after ``pip install -e .``::

    python benchmark.py
    python benchmark.py --orders 50000 --seed 7

Limitations (read before comparing numbers)
-------------------------------------------
- **Single-threaded, in-process.** No FastAPI, HTTP, or network. Results reflect the core
  matcher + order book only.
- **Workload is synthetic.** Prices and sides are uniform random over fixed ranges; mix of
  crosses, partial fills, and rests depends on those ranges, not on real market dynamics.
- **Not latency percentiles.** Only total time and average throughput; tail latency is not
  measured.
- **Machine-dependent.** Compare runs on the same OS, Python version, and hardware.
- **Logging:** ``log_event`` still builds JSON payloads on the hot path; the root logger is
  set to CRITICAL for this script to avoid I/O, but serialization work remains. Use as a
  relative baseline, not an absolute ceiling.
- **``python -O``** disables ``OrderBook`` invariant checks in ``__debug__`` builds; without
  ``-O``, debug overhead can lower throughput.

This script is meant for quick regression checks and learning, not exchange-grade benchmarking.
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
import time
from decimal import Decimal
from pathlib import Path

# Allow `python benchmark.py` from a clone without `pip install -e .`
_SRC = Path(__file__).resolve().parent / "src"
if _SRC.is_dir():
    sys.path.insert(0, str(_SRC))

from mini_exchange import MatchingEngine, Order, Side  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Benchmark MatchingEngine.submit_order throughput.")
    p.add_argument(
        "--orders",
        "-n",
        type=int,
        default=20_000,
        metavar="N",
        help="number of limit orders to submit (default: 20000)",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for reproducible order stream (default: 42)",
    )
    p.add_argument(
        "--price-min",
        type=int,
        default=50,
        help="inclusive min integer price (default: 50)",
    )
    p.add_argument(
        "--price-max",
        type=int,
        default=150,
        help="inclusive max integer price (default: 150)",
    )
    p.add_argument(
        "--qty-max",
        type=int,
        default=20,
        help="inclusive max integer quantity per order (default: 20)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.orders < 1:
        print("error: --orders must be at least 1", file=sys.stderr)
        sys.exit(2)
    if args.price_min > args.price_max or args.price_min < 1:
        print("error: need 1 <= --price-min <= --price-max", file=sys.stderr)
        sys.exit(2)
    if args.qty_max < 1:
        print("error: --qty-max must be at least 1", file=sys.stderr)
        sys.exit(2)

    logging.getLogger("mini_exchange").setLevel(logging.CRITICAL)

    random.seed(args.seed)
    engine = MatchingEngine()

    lo, hi = args.price_min, args.price_max
    qmax = args.qty_max

    orders = []
    for i in range(args.orders):
        side = Side.BUY if random.random() < 0.5 else Side.SELL
        price = Decimal(random.randint(lo, hi))
        qty = Decimal(random.randint(1, qmax))
        oid = f"id{i:08d}"
        orders.append(Order(oid, side, price, qty, timestamp=float(i)))

    t0 = time.perf_counter()
    for o in orders:
        engine.submit_order(o)
    elapsed = time.perf_counter() - t0

    rate = args.orders / elapsed if elapsed > 0 else float("inf")

    print(f"orders:        {args.orders}")
    print(f"seed:          {args.seed}")
    print(f"price range:   [{lo}, {hi}]  qty: [1, {qmax}]")
    print(f"elapsed_sec:   {elapsed:.6f}")
    print(f"throughput:    {rate:,.0f} orders/sec")


if __name__ == "__main__":
    main()
