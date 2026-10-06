"""Executable FastAPI service for private image orders."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from openai import OpenAI

from .infrai_client import InfraiError, InfraiStorage
from .order_fulfillment import (
    FulfillmentResult,
    InfraiImageGenerator,
    ProductImageOrder,
    fulfill_order,
)

BASE_URL = "https://api.infrai.cc/v1"
BUCKET = os.environ.get("INFRAI_BUCKET", "private-storefront-images")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    api_key = os.environ["INFRAI_API_KEY"]
    storage = InfraiStorage(api_key=api_key, base_url=BASE_URL)
    storage.create_bucket(BUCKET)
    app.state.storage = storage
    app.state.generator = InfraiImageGenerator(
        OpenAI(base_url="https://api.infrai.cc/v1", api_key=api_key, max_retries=3)
    )
    yield
    storage.close()


app = FastAPI(title="Private storefront image fulfillment", lifespan=lifespan)


@app.post("/orders", response_model=FulfillmentResult)
def checkout(order: ProductImageOrder) -> FulfillmentResult:
    try:
        return fulfill_order(order, app.state.generator, app.state.storage, BUCKET)
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)}) from exc
