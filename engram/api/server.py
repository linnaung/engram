"""Engram REST API — FastAPI server wrapping the engine."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from engram.engine import Engram
from engram.core.config import get_config

# Global engine instance
_engine: Engram | None = None


def get_engine() -> Engram:
    global _engine
    if _engine is None:
        _engine = Engram(get_config())
        _engine.initialize()
    return _engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_engine()
    yield
    if _engine:
        _engine.close()


app = FastAPI(
    title="Engram",
    description="Temporal Concept Graph with Probabilistic Decay — AI Memory Engine",
    version="0.1.0",
    lifespan=lifespan,
)


# --- Request/Response models ---

class IngestRequest(BaseModel):
    text: str = Field(..., description="Raw text to ingest as an episode")
    source: str = Field(default="conversation", description="Memory source label")


class IngestResponse(BaseModel):
    id: str
    content: str
    confidence: float
    half_life_days: float


class RecallRequest(BaseModel):
    query: str = Field(..., description="Natural language query")
    top_k: int = Field(default=5, ge=1, le=50)
    min_confidence: float = Field(default=0.05, ge=0.0, le=1.0)


class RecallItem(BaseModel):
    content: str
    layer: str
    score: float
    confidence: float
    source_id: str


class RecallResponse(BaseModel):
    results: list[RecallItem]
    count: int


class SynthesizeResponse(BaseModel):
    episodes_processed: int
    concepts_created: int
    beliefs_created: int
    edges_created: int
    episodes_garbage_collected: int


class StatusResponse(BaseModel):
    episodes: int
    concepts: int
    beliefs: int
    edges: int
    data_dir: str


class ForgetResponse(BaseModel):
    forgotten: bool
    memory_id: str


# --- Endpoints ---

@app.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest):
    """Ingest raw text as an L1 episodic memory."""
    engine = get_engine()
    episode = engine.ingest(req.text, source=req.source)
    return IngestResponse(
        id=episode.id,
        content=episode.content,
        confidence=episode.confidence,
        half_life_days=episode.half_life_days,
    )


@app.post("/recall", response_model=RecallResponse)
def recall(req: RecallRequest):
    """Hybrid recall across all memory layers."""
    engine = get_engine()
    results = engine.recall(req.query, top_k=req.top_k, min_confidence=req.min_confidence)
    items = [
        RecallItem(
            content=r.content,
            layer=r.layer,
            score=round(r.score, 4),
            confidence=round(r.confidence, 4),
            source_id=r.source_id,
        )
        for r in results
    ]
    return RecallResponse(results=items, count=len(items))


@app.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize():
    """Run the synthesis loop: Episodes → Concepts → Beliefs."""
    engine = get_engine()
    result = await engine.synthesize()
    return SynthesizeResponse(**result)


@app.get("/status", response_model=StatusResponse)
def status():
    """Get current memory statistics."""
    engine = get_engine()
    stats = engine.status()
    return StatusResponse(**stats)


@app.delete("/forget/{memory_id}", response_model=ForgetResponse)
def forget(memory_id: str):
    """Remove a specific memory by ID."""
    engine = get_engine()
    success = engine.forget(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")
    return ForgetResponse(forgotten=True, memory_id=memory_id)


@app.get("/health")
def health():
    """Health check."""
    return {"status": "ok", "service": "engram"}
