"""FastAPI application entrypoint for the matching service."""

from __future__ import annotations

from fastapi import FastAPI

from app.api import router

app = FastAPI(title="Mini Exchange Matching Service", version="0.1.0")
app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "matching"}
