from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.graph_runtime import init_graph_runtime, shutdown_graph_runtime
from app.routers import adjuster, claims, rules


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_graph_runtime()
    yield
    await shutdown_graph_runtime()


app = FastAPI(title="Insurance AI Platform API", version="0.1.0", lifespan=lifespan)

# The adjuster frontend (Vite dev server / static build) runs on a
# different origin than the API. No auth cookies are in play yet, so an
# open CORS policy is fine for this stage.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(claims.router)
app.include_router(adjuster.router)
app.include_router(rules.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
