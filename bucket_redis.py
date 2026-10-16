import redis

r = redis.Redis(decode_responses=True)

TOKEN_BUCKET_LUA = """
local key      = KEYS[1]
local capacity = tonumber(ARGV[1])
local rate     = tonumber(ARGV[2])
local now      = tonumber(ARGV[3])

-- 1. load this user's bucket
local data   = redis.call('HMGET', key, 'tokens', 'last')
local tokens = tonumber(data[1])
local last   = tonumber(data[2])

-- 2. first visit: start full
if tokens == nil then
  tokens = capacity
  last   = now
end

-- 3. refill
local elapsed = math.max(0, now - last)
tokens = math.min(capacity, tokens + elapsed * rate)

-- 4. take a token if we can
local allowed = 0
if tokens >= 1 then
  tokens  = tokens - 1
  allowed = 1
end

-- 5. save, and auto-delete idle buckets
redis.call('HSET', key, 'tokens', tokens, 'last', now)
redis.call('EXPIRE', key, math.ceil(capacity / rate) * 2)

-- 6. if blocked, how long until 1 token exists
local retry_after = 0
if allowed == 0 then
  retry_after = math.ceil((1 - tokens) / rate)
end

return {allowed, retry_after}
"""

bucket = r.register_script(TOKEN_BUCKET_LUA)

def allow(user, now, capacity=3, rate=0.5):
    allowed, retry_after = bucket(keys=[f"rl:{user}"], args=[capacity, rate, now])
    return allowed == 1, retry_after

if __name__ == "__main__":
    r.delete("rl:nandi")
    for t in [0, 0, 0, 0, 4, 100]:
        print(t, allow("nandi", t))