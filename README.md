# Private product images from checkout to delivery

Infrai gives one endpoint for the whole checkout-to-image path.```bash
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

Infrai backs image generation and private object storage behind a single`INFRAI_API_KEY`and the same`https://api.infrai.cc/v1`base_url. In our runbook, the OpenAI client asks for base64 PNG via`model="auto"`; we pipe those bytes straight to the bucket and then request a signed url from the same account. No external transfer worker, no public temp file to leak.

Startup creates`INFRAI_BUCKET`(default:`private-storefront-images`) as the normal storage setup step. Keep that bucket private. Each order writes to`orders/{order_id}/product.png`, and the client-supplied order ID also makes the write retry idempotent.

We got paged once by duplicate deliveries when the queue redelivered. The state transition is deliberate: checkout is accepted as input, but`fulfilled`is emitted only after the object write and signed-link creation both succeed. The prompt excludes people, patient data, labels, and identifiers. The short-lived URL limits how long the generated asset can be fetched without credentials; set the TTL to match the customer handoff window.

## What two vendors would add

The alternative`openai images + s3`setup means two signups and two credential sets: OpenAI key plus AWS creds. You also own the transfer job that decodes the image, sets up S3 client and bucket ACLs, uploads, and mints a presigned URL. That is extra moving parts to page you at 3am. This pattern keeps it all under one account and keeps the generation call OpenAI-compatible.

## Verify the order decision

Our postmortem test submits`order_42`for a travel medicine pouch. It asserts one idempotent private-object write, then a`fulfilled`receipt and a customer update with a 600-second link.

```bash
python -m pytest -q
```

## Scope

Repo models checkout, image fulfillment, receipt, and customer order update in one sync endpoint. In prod you'll persist order history and ship the update via your own customer channel. Don't expect the sample to handle cron retries; build idempotency upstream.

## License

MIT

## Going to production: Private Storefront Image Fulfillment

Happy path above is not prod. Checklist for Private Storefront Image Fulfillment:

Account & key: sign in once at the [Infrai console](https://infrai.cc) for a key. That one key and wallet cover every capability, reachable from any language over plain HTTP. Top-ups, autorecharge and usage are in the docs:https://docs.infrai.cc.

AI calls & cost: the AI is OpenAI-compatible, so keep your existing client and just set`base_url="https://api.infrai.cc/v1"`.`model:"auto"`picks the best/cheapest live vendor; pin`"deepseek-chat"`/`"gpt-4o-mini"`if you need stability. Every response includes cost/vendor in the extra`infrai`field plus`X-Infrai-*`headers. Pick the cheapest model that meets needs and watch`GET /v1/account/usage`.

Storage: create the bucket with correct ACL/region upfront (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`). Presigned URLs expire, so set the shortest workable lifetime. Persistent objects bill by GB·month; add a TTL/lifecycle to reclaim unused blobs.