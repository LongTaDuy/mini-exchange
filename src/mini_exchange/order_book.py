from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, Dict, Iterator, List, Mapping, Optional, Tuple

from mini_exchange.event_log import log_event
from mini_exchange.order import Order, Side


def _strictly_descending(prices: List[Decimal]) -> bool:
    return all(prices[i] > prices[i + 1] for i in range(len(prices) - 1))


def _strictly_ascending(prices: List[Decimal]) -> bool:
    return all(prices[i] < prices[i + 1] for i in range(len(prices) - 1))


@dataclass
class _BookNode:
    """Doubly-linked node so we can unlink a resting order in O(1) by id."""

    order: Order
    prev: Optional["_BookNode"] = field(default=None, repr=False)
    next: Optional["_BookNode"] = field(default=None, repr=False)


class _PriceLevel:
    """FIFO queue at one price: append at tail, match/cancel from head or by node."""

    __slots__ = ("head", "tail")

    def __init__(self) -> None:
        self.head: Optional[_BookNode] = None
        self.tail: Optional[_BookNode] = None

    def __bool__(self) -> bool:
        return self.head is not None

    def append(self, node: _BookNode) -> None:
        if self.tail is None:
            self.head = self.tail = node
            node.prev = node.next = None
        else:
            self.tail.next = node
            node.prev = self.tail
            node.next = None
            self.tail = node

    def peek_front(self) -> Optional[Order]:
        return self.head.order if self.head else None

    def pop_front(self) -> Optional[Order]:
        n = self.head
        if n is None:
            return None
        self._unlink(n)
        return n.order

    def remove_node(self, node: _BookNode) -> None:
        self._unlink(node)

    def _unlink(self, node: _BookNode) -> None:
        if node.prev is not None:
            node.prev.next = node.next
        else:
            self.head = node.next
        if node.next is not None:
            node.next.prev = node.prev
        else:
            self.tail = node.prev
        node.prev = node.next = None

    def iter_orders(self) -> Iterator[Order]:
        cur = self.head
        while cur is not None:
            yield cur.order
            cur = cur.next


@dataclass
class OrderBook:
    """
    Resting limit orders: FIFO per price level.

    **Data structures**
    - Each price level is a **doubly linked list** of ``_BookNode`` (FIFO: head = oldest).
      ``dict[order_id] -> _BookNode`` gives **O(1) cancellation** without scanning the queue.
      *Trade-off:* more pointers and unlink logic than a plain ``deque``; still easy to follow.
    - **Best bid / best ask** use ``heapq`` min-heaps (asks: price; bids: ``-price``), plus a
      **cache** of the current best price. The cache is **recomputed from level keys** whenever
      a side gains or loses a price level (rest or level deletion), so it always matches
      ``max(bids)`` / ``min(asks)``. ``best_*_price()`` is **O(1)** when the cache still points
      at a non-empty level. *Trade-off:* each new resting price level pays **O(#distinct
      prices on that side)** to refresh the extremum; heaps still provide the next best after
      the cached level is drained.

    **Lazy heap cleanup:** Empty levels delete their dict entry but stale prices may remain in
    heaps until popped in ``best_*_price()``.

    **Optional callback** ``on_order_removed`` is invoked with ``order_id`` whenever a resting
    order leaves the book (fill pop or cancel). Used by ``Exchange`` to keep a global id index.

    **Invariants** (``__debug__`` only): same as before — levels non-empty, FIFO order, book
    not crossed, index maps consistent with lists.
    """

    _bid_levels: Dict[Decimal, _PriceLevel] = field(default_factory=dict)
    _ask_levels: Dict[Decimal, _PriceLevel] = field(default_factory=dict)
    _bid_heap: List[Decimal] = field(default_factory=list)  # min-heap of -price
    _ask_heap: List[Decimal] = field(default_factory=list)  # min-heap of price
    _orders_by_id: Dict[str, Order] = field(default_factory=dict)
    _nodes_by_id: Dict[str, _BookNode] = field(default_factory=dict)
    # Cached best prices; None means unknown (recompute from heap on next read).
    _best_bid: Optional[Decimal] = field(default=None, repr=False)
    _best_ask: Optional[Decimal] = field(default=None, repr=False)
    on_order_removed: Optional[Callable[[str], None]] = field(default=None, repr=False)

    def _emit_removed(self, order_id: str) -> None:
        cb = self.on_order_removed
        if cb is not None:
            cb(order_id)

    def _sync_best_bid_cache(self) -> None:
        """Recompute cached best bid from live levels (max price). O(#distinct bid prices)."""
        self._best_bid = max(self._bid_levels) if self._bid_levels else None

    def _sync_best_ask_cache(self) -> None:
        """Recompute cached best ask from live levels (min price). O(#distinct ask prices)."""
        self._best_ask = min(self._ask_levels) if self._ask_levels else None

    def _check_invariants(self) -> None:
        """Internal consistency checks; no-op when running with ``python -O``."""
        if not __debug__:
            return

        for price, level in self._bid_levels.items():
            assert level.head, f"bid level at {price} is empty"
            for o in level.iter_orders():
                assert o.quantity > 0, f"bid {o.order_id} has non-positive quantity"
                assert o.side is Side.BUY, f"bid level contains non-BUY {o.order_id}"
                assert o.price == price, f"bid {o.order_id} price mismatch"

        for price, level in self._ask_levels.items():
            assert level.head, f"ask level at {price} is empty"
            for o in level.iter_orders():
                assert o.quantity > 0, f"ask {o.order_id} has non-positive quantity"
                assert o.side is Side.SELL, f"ask level contains non-SELL {o.order_id}"
                assert o.price == price, f"ask {o.order_id} price mismatch"

        bid_keys = sorted(self._bid_levels.keys(), reverse=True)
        assert _strictly_descending(bid_keys), "bid prices must be strictly descending"

        ask_keys = sorted(self._ask_levels.keys())
        assert _strictly_ascending(ask_keys), "ask prices must be strictly ascending"

        best_bid = max(self._bid_levels) if self._bid_levels else None
        best_ask = min(self._ask_levels) if self._ask_levels else None
        if best_bid is not None and best_ask is not None:
            assert best_bid < best_ask, (
                f"crossed book: best_bid={best_bid} best_ask={best_ask}"
            )

        seen_ids: List[str] = []
        for level in self._bid_levels.values():
            for o in level.iter_orders():
                seen_ids.append(o.order_id)
        for level in self._ask_levels.values():
            for o in level.iter_orders():
                seen_ids.append(o.order_id)
        assert len(seen_ids) == len(set(seen_ids)), "duplicate order_id in book queues"
        assert set(seen_ids) == set(self._orders_by_id.keys()), (
            "_orders_by_id out of sync with price levels"
        )
        assert set(seen_ids) == set(self._nodes_by_id.keys()), (
            "_nodes_by_id out of sync with price levels"
        )
        for oid, o in self._orders_by_id.items():
            assert o.order_id == oid
            levels = self._bid_levels if o.side is Side.BUY else self._ask_levels
            lvl = levels.get(o.price)
            assert lvl is not None, f"indexed order {oid} missing price level"
            node = self._nodes_by_id.get(oid)
            assert node is not None and node.order is o, f"node mismatch for {oid}"
            assert any(n is node for n in self._walk_nodes(lvl)), (
                f"indexed order {oid} not in level list"
            )

    @staticmethod
    def _walk_nodes(level: _PriceLevel) -> List[_BookNode]:
        out: List[_BookNode] = []
        cur = level.head
        while cur is not None:
            out.append(cur)
            cur = cur.next
        return out

    @property
    def bids(self) -> Mapping[Decimal, Tuple[Order, ...]]:
        return {
            p: tuple(self._bid_levels[p].iter_orders())
            for p in sorted(self._bid_levels.keys(), reverse=True)
            if self._bid_levels[p]
        }

    @property
    def asks(self) -> Mapping[Decimal, Tuple[Order, ...]]:
        return {
            p: tuple(self._ask_levels[p].iter_orders())
            for p in sorted(self._ask_levels.keys())
            if self._ask_levels[p]
        }

    def best_bid_price(self) -> Optional[Decimal]:
        cached = self._best_bid
        if cached is not None:
            level = self._bid_levels.get(cached)
            if level and level.head:
                return cached
            self._best_bid = None

        while self._bid_heap:
            p = -self._bid_heap[0]
            level = self._bid_levels.get(p)
            if level and level.head:
                self._best_bid = p
                return p
            heapq.heappop(self._bid_heap)
        self._best_bid = None
        return None

    def best_ask_price(self) -> Optional[Decimal]:
        cached = self._best_ask
        if cached is not None:
            level = self._ask_levels.get(cached)
            if level and level.head:
                return cached
            self._best_ask = None

        while self._ask_heap:
            p = self._ask_heap[0]
            level = self._ask_levels.get(p)
            if level and level.head:
                self._best_ask = p
                return p
            heapq.heappop(self._ask_heap)
        self._best_ask = None
        return None

    def peek_bid(self, price: Decimal) -> Optional[Order]:
        """Return the front (oldest) bid at `price`, or None if the level is empty/missing."""
        level = self._bid_levels.get(price)
        if not level:
            return None
        return level.peek_front()

    def peek_ask(self, price: Decimal) -> Optional[Order]:
        """Return the front (oldest) ask at `price`, or None if the level is empty/missing."""
        level = self._ask_levels.get(price)
        if not level:
            return None
        return level.peek_front()

    def pop_bid_front(self, price: Decimal) -> None:
        """Remove the front bid at `price` and delete the level if it becomes empty."""
        level = self._bid_levels.get(price)
        if not level or not level.head:
            return
        maker = level.pop_front()
        if maker is None:
            return
        oid = maker.order_id
        self._orders_by_id.pop(oid, None)
        self._nodes_by_id.pop(oid, None)
        if not level:
            del self._bid_levels[price]
            self._sync_best_bid_cache()
        self._emit_removed(oid)
        self._check_invariants()

    def pop_ask_front(self, price: Decimal) -> None:
        """Remove the front ask at `price` and delete the level if it becomes empty."""
        level = self._ask_levels.get(price)
        if not level or not level.head:
            return
        maker = level.pop_front()
        if maker is None:
            return
        oid = maker.order_id
        self._orders_by_id.pop(oid, None)
        self._nodes_by_id.pop(oid, None)
        if not level:
            del self._ask_levels[price]
            self._sync_best_ask_cache()
        self._emit_removed(oid)
        self._check_invariants()

    def get_order(self, order_id: str) -> Optional[Order]:
        """Fetch a resting order by `order_id`, or None if it is not present."""
        return self._orders_by_id.get(order_id)

    def cancel_order(self, order_id: str) -> Optional[Order]:
        """
        Cancel a resting order (remove it from the book).

        Matching is not performed as part of cancellation; the order is simply
        removed from its price level queue.
        """
        order = self._orders_by_id.get(order_id)
        if order is None:
            return None

        node = self._nodes_by_id.get(order_id)
        levels = self._bid_levels if order.side is Side.BUY else self._ask_levels
        level = levels.get(order.price)
        if level is None or node is None:
            self._orders_by_id.pop(order_id, None)
            self._nodes_by_id.pop(order_id, None)
            self._check_invariants()
            return None

        level.remove_node(node)
        self._orders_by_id.pop(order_id, None)
        self._nodes_by_id.pop(order_id, None)

        if not level:
            del levels[order.price]
            if order.side is Side.BUY:
                self._sync_best_bid_cache()
            else:
                self._sync_best_ask_cache()

        self._emit_removed(order_id)
        self._check_invariants()
        return order

    def bid_orders(self, price: Decimal) -> Tuple[Order, ...]:
        level = self._bid_levels.get(price)
        if level is None or not level.head:
            raise KeyError(f"no bid level at price {price}")
        return tuple(level.iter_orders())

    def ask_orders(self, price: Decimal) -> Tuple[Order, ...]:
        level = self._ask_levels.get(price)
        if level is None or not level.head:
            raise KeyError(f"no ask level at price {price}")
        return tuple(level.iter_orders())

    def rest_bid(self, order: Order) -> None:
        p = order.price
        if order.order_id in self._orders_by_id:
            log_event(
                "validation_failure",
                source="order_book",
                reason="duplicate order_id",
                order_id=order.order_id,
            )
            raise ValueError(f"duplicate order_id: {order.order_id}")
        new_level = p not in self._bid_levels
        node = _BookNode(order=order)
        self._orders_by_id[order.order_id] = order
        self._nodes_by_id[order.order_id] = node
        self._bid_levels.setdefault(p, _PriceLevel()).append(node)
        if new_level:
            heapq.heappush(self._bid_heap, -p)
        self._sync_best_bid_cache()
        self._check_invariants()

    def rest_ask(self, order: Order) -> None:
        p = order.price
        if order.order_id in self._orders_by_id:
            log_event(
                "validation_failure",
                source="order_book",
                reason="duplicate order_id",
                order_id=order.order_id,
            )
            raise ValueError(f"duplicate order_id: {order.order_id}")
        new_level = p not in self._ask_levels
        node = _BookNode(order=order)
        self._orders_by_id[order.order_id] = order
        self._nodes_by_id[order.order_id] = node
        self._ask_levels.setdefault(p, _PriceLevel()).append(node)
        if new_level:
            heapq.heappush(self._ask_heap, p)
        self._sync_best_ask_cache()
        self._check_invariants()

    def prune_empty_bid_level(self, price: Decimal) -> None:
        level = self._bid_levels.get(price)
        if level is not None and not level:
            del self._bid_levels[price]
            self._sync_best_bid_cache()
            self._check_invariants()

    def prune_empty_ask_level(self, price: Decimal) -> None:
        level = self._ask_levels.get(price)
        if level is not None and not level:
            del self._ask_levels[price]
            self._sync_best_ask_cache()
            self._check_invariants()
