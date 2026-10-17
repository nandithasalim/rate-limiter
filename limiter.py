import redis.asyncio as redis
from fastapi import HTTPException, Request

r = redis.Redis(decode_responses=True)

CAPACITY = 5      # burst of 5
RATE = 1          # then 1 request per second

TOKEN_BUCKET_LUA = """
local key      = KEYS[1]
local capacity = tonumber(ARGV[1])
local rate     = tonumber(ARGV[2])

-- use Redis's clock, so every worker agrees on the time
local t   = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000

local data   = redis.call('HMGET', key, 'tokens', 'last')
local tokens = tonumber(data[1])
local last   = tonumber(data[2])
if tokens == nil then
  tokens = capacity
  last   = now
end

tokens = math.min(capacity, tokens + math.max(0, now - last) * rate)

local allowed = 0
if tokens >= 1 then
  tokens  = tokens - 1
  allowed = 1
end

redis.call('HSET', key, 'tokens', tokens, 'last', now)
redis.call('EXPIRE', key, math.ceil(capacity / rate) * 2)

local retry_after = 0
if allowed == 0 then
  retry_after = math.ceil((1 - tokens) / rate)
end

return {allowed, retry_after, math.floor(tokens)}
"""

bucket = r.register_script(TOKEN_BUCKET_LUA)

async def rate_limit(request: Request):
    # who is this? API key if sent, else their IP
    client = request.headers.get("X-API-Key") or request.client.host
    allowed, retry_after, remaining = await bucket(
        keys=[f"rl:{client}"], args=[CAPACITY, RATE]
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many requests",
            headers={"Retry-After": str(retry_after)},
        )
    request.state.remaining = remaining