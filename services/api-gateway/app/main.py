"""FastAPI application entrypoint for the API gateway."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.client import close_client
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_client()


app = FastAPI(
    title="Mini Exchange API Gateway",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "gateway"}
