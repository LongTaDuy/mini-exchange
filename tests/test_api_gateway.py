"""Tests for the API Gateway (services/api-gateway).

The gateway forwards to the matching service over HTTP. To avoid requiring real
Docker services, we replace the gateway's shared `httpx.AsyncClient` with one
backed by `httpx.MockTransport`. This still exercises the real `forward()`
logic, including downstream error mapping.

Like the matching service, the gateway app is the top-level package `app`, so we
load it in isolation (purge cached `app*` modules, service dir at front of
sys.path).
"""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
import unittest
from pathlib import Path
from typing import List

import httpx
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
GATEWAY_DIR = REPO_ROOT / "services" / "api-gateway"


def _load_gateway():
    for name in [m for m in list(sys.modules) if m == "app" or m.startswith("app.")]:
        del sys.modules[name]
    path = str(GATEWAY_DIR)
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)
    main = importlib.import_module("app.main")
    client = importlib.import_module("app.client")
    return main, client


_main, _client = _load_gateway()


class TestApiGateway(unittest.TestCase):
    def setUp(self) -> None:
        self.received: List[httpx.Request] = []
        # Reset any existing shared client before injecting the mock.
        asyncio.run(_client.close_client())

    def tearDown(self) -> None:
        asyncio.run(_client.close_client())

    def _install_mock(self, handler) -> None:
        def _capture(request: httpx.Request) -> httpx.Response:
            self.received.append(request)
            return handler(request)

        _client._client = httpx.AsyncClient(
            base_url="http://matching-service:8001",
            transport=httpx.MockTransport(_capture),
        )

    def test_health(self) -> None:
        client = TestClient(_main.app)
        r = client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "ok", "service": "gateway"})

    def test_forwards_submit_order(self) -> None:
        downstream_body = {
            "symbol": "BTC-USD",
            "order": {
                "order_id": "s1",
                "side": "sell",
                "price": "100",
                "quantity_submitted": "5",
                "quantity_remaining": "5",
                "resting": True,
                "timestamp": 0.0,
            },
            "trades": [],
            "book": {"best_bid": None, "best_ask": "100"},
        }
        self._install_mock(lambda req: httpx.Response(200, json=downstream_body))

        client = TestClient(_main.app)
        payload = {
            "symbol": "BTC-USD",
            "order_id": "s1",
            "side": "sell",
            "price": "100",
            "quantity": "5",
        }
        r = client.post("/orders", json=payload)

        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), downstream_body)
        # The request was forwarded to the matching service unchanged.
        self.assertEqual(len(self.received), 1)
        fwd = self.received[0]
        self.assertEqual(fwd.method, "POST")
        self.assertEqual(fwd.url.path, "/orders")
        self.assertEqual(json.loads(fwd.read()), payload)

    def test_forwards_downstream_400_error(self) -> None:
        err_body = {"detail": {"code": "invalid_order", "message": "quantity must be > 0"}}
        self._install_mock(lambda req: httpx.Response(400, json=err_body))

        client = TestClient(_main.app)
        r = client.post(
            "/orders",
            json={
                "symbol": "BTC-USD",
                "order_id": "x",
                "side": "buy",
                "price": "1",
                "quantity": "0",
            },
        )
        self.assertEqual(r.status_code, 400, r.text)
        self.assertEqual(
            r.json()["detail"],
            {"code": "invalid_order", "message": "quantity must be > 0"},
        )

    def test_forwards_downstream_404_error(self) -> None:
        err_body = {"detail": {"code": "not_found", "message": "Resting order not found"}}
        self._install_mock(lambda req: httpx.Response(404, json=err_body))

        client = TestClient(_main.app)
        r = client.get("/orders/missing")
        self.assertEqual(r.status_code, 404, r.text)
        self.assertEqual(r.json()["detail"]["code"], "not_found")

    def test_upstream_connection_error_returns_503(self) -> None:
        def _boom(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        self._install_mock(_boom)

        client = TestClient(_main.app)
        r = client.get("/orderbook/BTC-USD")
        self.assertEqual(r.status_code, 503, r.text)
        self.assertEqual(r.json()["detail"]["code"], "upstream_unavailable")

    def test_upstream_timeout_returns_504(self) -> None:
        def _slow(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("timed out", request=request)

        self._install_mock(_slow)

        client = TestClient(_main.app)
        r = client.get("/orderbook/BTC-USD")
        self.assertEqual(r.status_code, 504, r.text)
        self.assertEqual(r.json()["detail"]["code"], "upstream_timeout")


if __name__ == "__main__":
    unittest.main()
