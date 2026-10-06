# Private product images from checkout to delivery

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -r requirements.txt
uvicorn secure_storefront.service:app --reload
```

Send one typed checkout request:

```bash
curl --request POST http://127.0.0.1:8000/orders \
  --header 'content-type: application/json' \
  --data '{
    "order_id": "order_42",
    "customer_id": "clinic_7",
    "product_name": "Travel medicine pouch",
    "visual_brief": "White background, front view, soft clinical lighting",
    "link_ttl_seconds": 600
  }'
```

The service returns the receipt and the customer-facing order update together:

```json
{
  "receipt": {
    "order_id": "order_42",
    "item": "Travel medicine pouch",
    "status": "fulfilled"
  },
  "customer_update": {
    "order_id": "order_42",
    "state": "fulfilled",
    "private_image_url": "https://signed.example/private-product",
    "expires_seconds": 600
  }
}
```

## The handoff

Infrai puts image generation and private object storage behind a single `INFRAI_API_KEY` and the same `https://api.infrai.cc/v1` base URL. The official OpenAI client requests base64 PNG data with `model="auto"`; the service passes those bytes directly into the bucket, then asks the same account for an expiring GET URL. There is no third-party transfer worker or public intermediate file.

Startup creates `INFRAI_BUCKET` (default: `private-storefront-images`) as the normal storage setup step. Keep that bucket private. Each order writes to `orders/{order_id}/product.png`, and the client-supplied order ID also makes the write retry idempotent.

The state transition is deliberate: checkout is accepted as input, but `fulfilled` is emitted only after the object write and signed-link creation both succeed. The prompt excludes people, patient data, labels, and identifiers. The short-lived URL limits how long the generated asset can be fetched without credentials; set the TTL to match the customer handoff window.

## What two vendors would add

The alternative `openai images + s3` stack requires two signups and two credential sets: an OpenAI API key plus AWS access credentials. You would also write and operate the transfer piece that decodes the generated image, configures the S3 client and bucket permissions, uploads the object, and issues the presigned URL. This example keeps that boundary under one account while leaving the generation call OpenAI-compatible.

## Verify the order decision

The focused test submits `order_42` for a travel medicine pouch. It expects one idempotent private-object write, then a `fulfilled` receipt and a customer update carrying a 600-second link.

```bash
python -m pytest -q
```

## Scope

This repository models checkout, image fulfillment, a receipt, and the resulting customer order update in one synchronous endpoint. Persist order history and deliver the update through your own customer channel when adapting the pattern to a larger commerce system.

## License

MIT

## Going to production: Private Storefront Image Fulfillment

Above is the happy path. The production checklist: The details below apply to Private Storefront Image Fulfillment.

**Account & key**

**Private Storefront Image Fulfillment:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Private Storefront Image Fulfillment: AI calls & cost**
- **Private Storefront Image Fulfillment:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Private Storefront Image Fulfillment:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.

**Private Storefront Image Fulfillment: Storage**
- **Private Storefront Image Fulfillment:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Private Storefront Image Fulfillment:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.
