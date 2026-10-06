from secure_storefront.order_fulfillment import ProductImageOrder, fulfill_order


class FixedGenerator:
    def generate_png(self, prompt: str) -> str:
        assert "No people, patient data, labels, or identifiers" in prompt
        return "cG5n"


class RecordingStorage:
    def __init__(self) -> None:
        self.puts: list[tuple[str, str, str, str]] = []

    def put_image(self, bucket: str, key: str, data_base64: str, idempotency_key: str) -> None:
        self.puts.append((bucket, key, data_base64, idempotency_key))

    def presign_download(self, bucket: str, key: str, expires_seconds: int) -> str:
        assert (bucket, key, expires_seconds) == (
            "private-images",
            "orders/order_42/product.png",
            600,
        )
        return "https://signed.example/private-product"


def test_checkout_fulfills_only_after_private_image_handoff() -> None:
    storage = RecordingStorage()
    order = ProductImageOrder(
        order_id="order_42",
        customer_id="clinic_7",
        product_name="Travel medicine pouch",
        visual_brief="White background, front view, soft clinical lighting",
        link_ttl_seconds=600,
    )

    result = fulfill_order(order, FixedGenerator(), storage, "private-images")

    assert storage.puts == [
        (
            "private-images",
            "orders/order_42/product.png",
            "cG5n",
            "order_42-product-image",
        )
    ]
    assert result.receipt.status == "fulfilled"
    assert result.customer_update.model_dump() == {
        "order_id": "order_42",
        "state": "fulfilled",
        "private_image_url": "https://signed.example/private-product",
        "expires_seconds": 600,
    }
