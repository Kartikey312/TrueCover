from fastapi import FastAPI

from app.routers import adjuster, claims

app = FastAPI(title="Insurance AI Platform API", version="0.1.0")

app.include_router(claims.router)
app.include_router(adjuster.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
