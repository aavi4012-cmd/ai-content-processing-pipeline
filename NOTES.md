# Engineering Decisions & Tradeoffs

## Why a Message Queue (Celery + Redis)?

LLM APIs are inherently slow — latency ranges from 500ms to 30s+ depending on the provider and prompt complexity. Calling the LLM synchronously inside a FastAPI request handler would:

- Keep HTTP connections open indefinitely, exhausting API worker threads.
- Cause cascading 504 Gateway Timeouts under load.
- Make it impossible to retry failed calls transparently.

By publishing tasks to a Redis-backed Celery queue, the API returns an immediate `submission_id` in under 50ms. The client can then poll for status or receive a webhook callback when done.

## Why Exponential Backoff Retries?

Public LLM APIs (OpenAI, Anthropic, etc.) frequently return:
- **429 Too Many Requests** — rate limiting
- **502/503** — transient gateway errors
- **Timeouts** — network latency spikes

Our strategy:
- `autoretry_for=(Exception,)` catches all transient failures automatically.
- `retry_backoff=True` applies exponential delays (1s → 2s → 4s → ...) to avoid hammering a degraded API.
- `retry_backoff_max=60` caps the maximum delay at 60 seconds.
- `max_retries=3` (configurable) prevents zombie tasks — after exhaustion, the submission is marked `failed` with the error reason stored.

## How Validation Works

This is a critical safety layer. LLMs are probabilistic — even with `response_format={"type": "json_object"}`, the output may:
- Miss required fields
- Use unexpected values (e.g., "Positive" instead of "positive")
- Include extra hallucinated keys

Our defense:
1. **OpenAI JSON Mode** — forces the LLM to return valid JSON syntax.
2. **Pydantic `LLMOutput` Schema** — validates the structure, enforcing `Literal["positive", "negative", "neutral"]` for sentiment. If any field is wrong, a `ValidationError` is raised.
3. **Retry on Validation Failure** — the error propagates to Celery, which retries the task. LLMs often self-correct on a second attempt.

## Idempotent Processing

Workers check `submission.status == "completed"` before processing. If a task is accidentally delivered twice (which can happen with at-least-once queue semantics), the second execution short-circuits immediately. This prevents:
- Duplicate LLM API calls (saving cost)
- Race conditions on result storage

## Row-Level Database Locking

The worker uses `SELECT ... FOR UPDATE` (`with_for_update()` in SQLAlchemy) when retrieving a submission. This acquires an exclusive row lock in PostgreSQL, guaranteeing that no other worker can read or modify the same row simultaneously — even if multiple workers attempt to process the same ID.

## Webhook Notifications

In addition to polling (`GET /submissions/{id}`), clients can provide a `webhook_url` in the submission payload. Upon completion (or permanent failure), the worker fires a best-effort POST request to this URL. This follows actual production patterns where push notifications eliminate expensive polling from the client side.

Webhook failures are logged but never block the pipeline — they are fire-and-forget by design.

## Request Tracing

Every API response includes an `X-Request-ID` header — a short unique identifier that can be correlated with server logs. This is essential for debugging issues in production where multiple requests are processed concurrently.

## Tradeoffs Considered

| Decision | Chosen | Alternative | Rationale |
|---|---|---|---|
| **ID format** | UUID v4 | Auto-increment | Non-guessable, safe to expose in URLs |
| **Database driver** | Sync SQLAlchemy | Async (asyncpg) | Celery workers run synchronously; async provides no benefit here |
| **Polling vs Webhooks** | Both | Polling only | Webhooks reduce client-side load; polling ensures compatibility |
| **Worker concurrency** | `-P solo` | Prefork / Gevent | Solo is safer on Windows/Docker; can switch to prefork for Linux production |
| **Mock LLM fallback** | Yes | Require API key | Allows reviewers to test the full pipeline without any API costs |
| **Cloud deployment** | render.yaml (free) | AWS ECS / K8s | Zero-cost hosting ideal for portfolio projects; IaC pattern still demonstrated |
| **LLM timeout** | 30s configurable | No timeout | Prevents indefinite hangs; configurable via `LLM_TIMEOUT` env var |
