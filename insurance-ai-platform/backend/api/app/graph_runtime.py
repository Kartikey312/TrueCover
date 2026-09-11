"""Owns the compiled claims-processing graph and its Postgres-backed
checkpointer for the lifetime of the API process.

The graph itself (backend/graph) stays DB-free; this module is the one
place that gives it a real, durable checkpointer so a paused human review
survives an API restart, and exposes the compiled graph for the pipeline
service to invoke/resume.
"""

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph

from graph.build_graph import build_graph

from app.config import settings

_compiled_graph: CompiledStateGraph | None = None
_saver_context = None


def _psycopg_dsn(database_url: str) -> str:
    """AsyncPostgresSaver needs a plain postgresql:// DSN for psycopg, not
    the postgresql+asyncpg:// URL SQLAlchemy uses elsewhere in this app.
    """
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


async def init_graph_runtime() -> None:
    global _compiled_graph, _saver_context

    _saver_context = AsyncPostgresSaver.from_conn_string(_psycopg_dsn(settings.database_url))
    saver = await _saver_context.__aenter__()
    await saver.setup()
    _compiled_graph = build_graph(saver)


async def shutdown_graph_runtime() -> None:
    global _compiled_graph, _saver_context
    if _saver_context is not None:
        await _saver_context.__aexit__(None, None, None)
        _saver_context = None
    _compiled_graph = None


def get_compiled_graph() -> CompiledStateGraph:
    if _compiled_graph is None:
        raise RuntimeError("Graph runtime not initialized -- call init_graph_runtime() at startup.")
    return _compiled_graph
