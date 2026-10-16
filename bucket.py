CAPACITY = 3
RATE = 0.5          # tokens per second
store = {}

def allow(user, now):
    if user not in store:
        store[user] = {"tokens": CAPACITY, "last": now}
    b = store[user]

    b["tokens"] = min(CAPACITY, b["tokens"] + (now - b["last"]) * RATE)
    b["last"] = now

    if b["tokens"] >= 1:
        b["tokens"] -= 1
        return True
    return False

for t in [0, 0, 0, 0, 4, 100]:
    print(t, allow("nandi", t))