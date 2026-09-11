from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.graph_runtime import init_graph_runtime, shutdown_graph_runtime
from app.routers import adjuster, claims


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_graph_runtime()
    yield
    await shutdown_graph_runtime()


app = FastAPI(title="Insurance AI Platform API", version="0.1.0", lifespan=lifespan)

app.include_router(claims.router)
app.include_router(adjuster.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
