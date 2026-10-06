"""Checkout-to-fulfillment workflow for private product images."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from openai import OpenAI
from pydantic import BaseModel, Field

class ProductImageOrder(BaseModel):
    order_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    customer_id: str = Field(min_length=1, max_length=80)
    product_name: str = Field(min_length=1, max_length=120)
    visual_brief: str = Field(min_length=10, max_length=1200)
    link_ttl_seconds: int = Field(default=900, ge=60, le=3600)


class Receipt(BaseModel):
    order_id: str
    item: str
    status: str


class CustomerOrderUpdate(BaseModel):
    order_id: str
    state: str
    private_image_url: str
    expires_seconds: int


class FulfillmentResult(BaseModel):
    receipt: Receipt
    customer_update: CustomerOrderUpdate


class ImageGenerator(Protocol):
    generate_png: Callable[[str], str]


class ObjectStore(Protocol):
    put_image: Callable[[str, str, str, str], None]
    presign_download: Callable[[str, str, int], str]


@dataclass
class InfraiImageGenerator:
    client: OpenAI

    def generate_png(self, prompt: str) -> str:
        image = self.client.images.generate(
            model="auto",
            prompt=prompt,
            size="1024x1024",
            response_format="b64_json",
        )
        encoded = image.data[0].b64_json
        if not encoded:
            raise RuntimeError("Image response did not contain PNG data")
        return encoded


def fulfill_order(
    order: ProductImageOrder,
    generator: ImageGenerator,
    storage: ObjectStore,
    bucket: str,
) -> FulfillmentResult:
    object_key = f"orders/{order.order_id}/product.png"
    prompt = (
        f"E-commerce product image for {order.product_name}. "
        f"{order.visual_brief}. No people, patient data, labels, or identifiers."
    )
    png_base64 = generator.generate_png(prompt)
    storage.put_image(
        bucket,
        object_key,
        png_base64,
        idempotency_key=f"{order.order_id}-product-image",
    )
    private_url = storage.presign_download(bucket, object_key, order.link_ttl_seconds)

    return FulfillmentResult(
        receipt=Receipt(order_id=order.order_id, item=order.product_name, status="fulfilled"),
        customer_update=CustomerOrderUpdate(
            order_id=order.order_id,
            state="fulfilled",
            private_image_url=private_url,
            expires_seconds=order.link_ttl_seconds,
        ),
    )
