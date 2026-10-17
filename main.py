from fastapi import Depends, FastAPI, Request, Response
from limiter import CAPACITY, rate_limit

app = FastAPI()

@app.get("/ping", dependencies=[Depends(rate_limit)])
async def ping(request: Request, response: Response):
    response.headers["X-RateLimit-Limit"] = str(CAPACITY)
    response.headers["X-RateLimit-Remaining"] = str(request.state.remaining)
    return {"ok": True}