import asyncio, time, httpx

N, CAPACITY, RATE = 1000, 5, 1

async def main():
    limits = httpx.Limits(max_connections=200)
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", limits=limits) as c:
        start = time.time()
        rs = await asyncio.gather(
            *[c.get("/ping", headers={"X-API-Key": "loadtest"}) for _ in range(N)]
        )
        dur = time.time() - start

    ok = sum(r.status_code == 200 for r in rs)
    blocked = sum(r.status_code == 429 for r in rs)
    max_allowed = int(CAPACITY + RATE * dur)
    print(f"{N} requests in {dur:.2f}s → {ok} allowed, {blocked} blocked (max allowed {max_allowed})")
    assert ok <= max_allowed, "LIMIT LEAKED"
    print("✅ limit held")

asyncio.run(main())