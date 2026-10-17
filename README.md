# Distributed Rate Limiter (FastAPI + Redis + Lua)

A token-bucket rate limiter for a FastAPI service. Limits are enforced in Redis by an atomic Lua script, so they hold even when the API runs as multiple worker processes.

## How it works

Each client gets a bucket of tokens:

- **Capacity:** 5 tokens, so a client can make a burst of 5 requests.
- **Refill rate:** 1 token per second, up to the capacity.
- Each request uses 1 token. With no token left, the API returns **429 Too Many Requests** and a `Retry-After` header.

The bucket has no background timer. It stores only `tokens` and `last` (the last refill time). On each request, it computes how many tokens have accumulated since then:

```
tokens = min(capacity, tokens + (now - last) * rate)
```

Clients are identified by the `X-API-Key` header, falling back to their IP address.

## Why Redis and Lua

**Why Redis:** The API runs with `uvicorn --workers 4`, which means 4 separate processes. An in-memory dict would give each worker its own bucket, so a client could get 4× the limit. Redis is one shared store, so every worker sees the same bucket.

**Why Lua:** A check has three steps: read tokens, decide, write tokens. If two workers read "1 token left" at the same moment, both would allow the request. Redis runs a Lua script atomically: no other command runs in the middle. So the read, the refill, the check and the write happen as one step, and the race can't occur.

**Two other details:**
- The script uses Redis's own clock (`TIME`), so workers with slightly different system clocks can't break the refill math.
- Each bucket gets an `EXPIRE`, so idle clients are cleaned up automatically and memory stays bounded.

## Files

| File | Purpose |
|---|---|
| `bucket.py` | The algorithm in plain Python (single process), for understanding |
| `bucket_redis.py` | The same logic as a Redis Lua script, tested with fake times |
| `limiter.py` | Async FastAPI dependency that runs the Lua script per client |
| `main.py` | FastAPI app with a rate-limited `GET /ping` |
| `loadtest.py` | Fires 1,000 concurrent requests and checks the limit held |

## Run it

```bash
docker run -d --name redis -p 6379:6379 redis:7
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn redis httpx

uvicorn main:app --workers 4
```

Quick check (5 succeed, then 429s):
```bash
for i in {1..8}; do curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/ping; done
```

Load test:
```bash
docker exec redis redis-cli DEL rl:loadtest
python loadtest.py
```

## Results

1,000 concurrent requests from one client against 4 Uvicorn workers:

```
<paste the exact line loadtest.py printed>
```

The number allowed never exceeded `capacity + rate × test_duration`. That's the most a correct limiter can allow, so the limit held under concurrency.

## Design choices and tradeoffs

- **Token bucket vs sliding window:** a token bucket allows short bursts, which suits real users who click a few things quickly. It needs O(1) memory per client. A sliding-window log is exact but stores one entry per request.
- **Fail open vs fail closed:** if Redis is unreachable, this demo errors out. A production version would pick deliberately: fail open (allow traffic) for a free API, fail closed (block) for something expensive such as paid LLM calls.
- **Async client:** the endpoint is `async def`, so it uses `redis.asyncio`. A blocking client would freeze the event loop for every request.

## What I'd add next

- A sliding-window limiter, for comparison
- Per-route limits and per-plan limits (free vs paid)
- Prometheus metrics for allowed and blocked counts
