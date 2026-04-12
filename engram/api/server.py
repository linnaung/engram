"""Engram REST API: FastAPI server wrapping the engine."""

from __future__ import annotations

import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from engram.engine import Engram
from engram.core.config import get_config
from engram.core.decay import compute_confidence

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
    description="Temporal Concept Graph with Probabilistic Decay",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files if built
_ui_dist = Path(__file__).parent.parent / "ui" / "dist"
if _ui_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(_ui_dist / "assets")), name="assets")


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
    facts_created: int = 0
    fact_contradictions: int = 0
    concepts_merged: int = 0
    beliefs_created: int
    edges_created: int
    contradictions_resolved: int = 0
    episodes_garbage_collected: int


class StatusResponse(BaseModel):
    episodes: int
    concepts: int
    facts: int = 0
    beliefs: int
    edges: int
    sessions: int = 0
    context_loaded: bool = False
    data_dir: str


class FactItem(BaseModel):
    subject: str
    predicate: str
    object: str
    subject_type: str
    object_type: str
    confidence: float
    id: str


class FactsResponse(BaseModel):
    facts: list[FactItem]
    count: int


class ForgetResponse(BaseModel):
    forgotten: bool
    memory_id: str


class SessionItem(BaseModel):
    id: str
    title: str
    created_at: str
    ontology_path: str | None = None
    last_message: str | None = None
    message_count: int = 0


class MessageItem(BaseModel):
    id: str
    role: str
    content: str
    created_at: str
    memories_used: list[dict] = []


class CreateSessionRequest(BaseModel):
    title: str = Field(default="New Chat")


class SessionChatRequest(BaseModel):
    message: str = Field(..., description="User message")


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    history: list[dict[str, str]] = Field(default_factory=list, description="Conversation history [{role, content}]")


class ChatMemory(BaseModel):
    content: str
    layer: str
    score: float
    confidence: float


class ChatResponse(BaseModel):
    response: str
    memories_used: list[ChatMemory]


class EpisodeItem(BaseModel):
    id: str
    content: str
    source: str
    timestamp: str
    confidence: float


class ConceptItem(BaseModel):
    id: str
    summary: str
    confidence: float
    reinforcement_count: int


class BeliefItem(BaseModel):
    id: str
    principle: str
    confidence: float


class EdgeItem(BaseModel):
    source: str
    target: str
    relation: str
    weight: float


class GraphResponse(BaseModel):
    beliefs: list[BeliefItem]
    edges: list[EdgeItem]


class ContextInfo(BaseModel):
    loaded: bool
    types: list[str] = []
    predicates: list[str] = []
    type_count: int = 0
    predicate_count: int = 0


class SimulateStep(BaseModel):
    day: int
    episodes: int
    concepts: int
    facts: int
    beliefs: int


class SimulateResponse(BaseModel):
    steps: list[SimulateStep]
    total_episodes: int
    total_concepts: int
    total_facts: int
    total_beliefs: int


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


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Chat with Ollama, augmented by Engram memory.

    Ingests the user message, recalls relevant memories,
    injects them into the Ollama prompt, and returns the response.
    """
    engine = get_engine()
    result = engine.chat(req.message, history=req.history or None)
    memories = [
        ChatMemory(
            content=m["content"], layer=m["layer"],
            score=m["score"], confidence=m["confidence"],
        )
        for m in result["memories_used"]
    ]
    return ChatResponse(response=result["response"], memories_used=memories)


# --- Session endpoints ---

@app.get("/sessions")
def list_sessions():
    """List all chat sessions."""
    engine = get_engine()
    sessions = engine.sessions.list_sessions()
    return {
        "sessions": [
            SessionItem(
                id=s.id, title=s.title, created_at=s.created_at,
                ontology_path=s.ontology_path, last_message=s.last_message,
                message_count=s.message_count,
            ).model_dump()
            for s in sessions
        ]
    }


@app.post("/sessions")
def create_session(req: CreateSessionRequest):
    """Create a new chat session."""
    engine = get_engine()
    session = engine.sessions.create_session(title=req.title)
    return SessionItem(
        id=session.id, title=session.title, created_at=session.created_at,
    ).model_dump()


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Get a session with its message history."""
    engine = get_engine()
    session = engine.sessions.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    messages = engine.sessions.get_messages(session_id)
    return {
        "session": SessionItem(
            id=session.id, title=session.title, created_at=session.created_at,
            ontology_path=session.ontology_path, message_count=session.message_count,
        ).model_dump(),
        "messages": [
            MessageItem(
                id=m.id, role=m.role, content=m.content,
                created_at=m.created_at, memories_used=m.memories_used,
            ).model_dump()
            for m in messages
        ],
    }


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """Delete a session and all its messages."""
    engine = get_engine()
    if not engine.sessions.delete_session(session_id):
        raise HTTPException(404, "Session not found")
    return {"deleted": True}


@app.post("/sessions/{session_id}/chat", response_model=ChatResponse)
def session_chat(session_id: str, req: SessionChatRequest):
    """Send a message in a session context."""
    engine = get_engine()
    session = engine.sessions.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    # Load session-specific ontology if set
    if session.ontology_path:
        try:
            engine.load_context(session.ontology_path)
        except Exception:
            pass

    result = engine.chat(req.message, session_id=session_id)
    memories = [
        ChatMemory(
            content=m["content"], layer=m["layer"],
            score=m["score"], confidence=m["confidence"],
        )
        for m in result["memories_used"]
    ]
    return ChatResponse(response=result["response"], memories_used=memories)


@app.post("/sessions/{session_id}/ontology")
async def upload_session_ontology(session_id: str, file: UploadFile = File(...)):
    """Upload an ontology for a specific session."""
    engine = get_engine()
    session = engine.sessions.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    suffix = Path(file.filename or "upload.ttl").suffix.lower()
    if suffix not in (".ttl", ".jsonld"):
        raise HTTPException(400, f"Unsupported format: {suffix}")

    content = await file.read()
    saved_path = engine.config.data_dir / f"ontology_{session_id[:8]}{suffix}"
    saved_path.write_bytes(content)

    try:
        engine.load_context(str(saved_path))
    except Exception as e:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(400, f"Failed to parse ontology: {e}")

    # Save ontology path to session
    engine.sessions.conn.execute(
        "UPDATE sessions SET ontology_path = ? WHERE id = ?",
        (str(saved_path), session_id),
    )
    engine.sessions.conn.commit()

    ctx = engine.context
    return {
        "loaded": True,
        "types": ctx.list_types() if ctx else [],
        "predicates": ctx.list_predicates() if ctx else [],
    }


@app.post("/recall", response_model=RecallResponse)
def recall(req: RecallRequest):
    """Hybrid recall across all memory layers."""
    engine = get_engine()
    results = engine.recall(req.query, top_k=req.top_k, min_confidence=req.min_confidence)
    items = [
        RecallItem(
            content=r.content, layer=r.layer,
            score=round(r.score, 4), confidence=round(r.confidence, 4),
            source_id=r.source_id,
        )
        for r in results
    ]
    return RecallResponse(results=items, count=len(items))


@app.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize():
    """Run the synthesis loop."""
    engine = get_engine()
    result = await engine.synthesize()
    return SynthesizeResponse(**result)


@app.get("/status", response_model=StatusResponse)
def status():
    """Get current memory statistics."""
    engine = get_engine()
    stats = engine.status()
    return StatusResponse(**stats)


@app.get("/episodes")
def list_episodes(limit: int = 50):
    """List recent episodes."""
    engine = get_engine()
    episodes = engine.episodes.list_active(limit=limit)
    return {
        "episodes": [
            EpisodeItem(
                id=e.id, content=e.content, source=e.source,
                timestamp=e.timestamp.isoformat(),
                confidence=round(e.confidence, 4),
            ).model_dump()
            for e in episodes
        ],
        "count": len(episodes),
    }


@app.get("/concepts")
def list_concepts(limit: int = 50):
    """List concepts."""
    engine = get_engine()
    results = engine.concepts.collection.get(
        include=["documents", "metadatas"],
        limit=limit,
    )
    items = []
    for i in range(len(results["ids"])):
        meta = results["metadatas"][i]
        items.append(ConceptItem(
            id=results["ids"][i],
            summary=results["documents"][i],
            confidence=meta.get("initial_confidence", 0.0),
            reinforcement_count=meta.get("reinforcement_count", 0),
        ).model_dump())
    return {"concepts": items, "count": len(items)}


@app.get("/facts", response_model=FactsResponse)
def list_facts(subject: str | None = None, predicate: str | None = None, object: str | None = None):
    """Query structured facts (L2.5 triples)."""
    engine = get_engine()
    results = engine.facts.query(subject=subject, predicate=predicate, object=object)
    items = [
        FactItem(
            subject=f.subject, predicate=f.predicate, object=f.object,
            subject_type=f.subject_type, object_type=f.object_type,
            confidence=round(f.confidence, 4), id=f.id,
        )
        for f in results
    ]
    return FactsResponse(facts=items, count=len(items))


@app.get("/beliefs", response_model=GraphResponse)
def list_beliefs():
    """List all beliefs and edges for graph visualization."""
    engine = get_engine()
    beliefs = engine.beliefs.list_beliefs()
    edges_data = []
    for u, v, data in engine.beliefs.graph.edges(data=True):
        edges_data.append(EdgeItem(
            source=u, target=v,
            relation=data.get("relation", "related"),
            weight=data.get("weight", 0.5),
        ))
    belief_items = [
        BeliefItem(id=b.id, principle=b.principle, confidence=round(b.confidence, 4))
        for b in beliefs
    ]
    return GraphResponse(beliefs=belief_items, edges=edges_data)


@app.get("/context", response_model=ContextInfo)
def get_context():
    """Get loaded ontology context info."""
    engine = get_engine()
    ctx = engine.context
    if ctx is None:
        return ContextInfo(loaded=False)
    types = ctx.list_types()
    predicates = ctx.list_predicates()
    return ContextInfo(
        loaded=True,
        types=types,
        predicates=predicates,
        type_count=len(types),
        predicate_count=len(predicates),
    )


@app.post("/context/upload")
async def upload_context(file: UploadFile = File(...)):
    """Upload an ontology file (.ttl or .jsonld). Persists to data dir."""
    engine = get_engine()

    suffix = Path(file.filename or "upload.ttl").suffix.lower()
    if suffix not in (".ttl", ".jsonld"):
        raise HTTPException(400, f"Unsupported format: {suffix}. Use .ttl or .jsonld")

    content = await file.read()

    # Save directly to the data dir so load_context can persist it
    saved_path = engine.config.data_dir / f"ontology{suffix}"
    saved_path.write_bytes(content)

    try:
        engine.load_context(str(saved_path))
    except Exception as e:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(400, f"Failed to parse ontology: {e}")

    ctx = engine.context
    return {
        "loaded": True,
        "types": ctx.list_types() if ctx else [],
        "predicates": ctx.list_predicates() if ctx else [],
        "filename": file.filename,
    }


@app.get("/simulate")
def simulate(days: int = 365, step: int = 30):
    """Simulate memory decay over time."""
    engine = get_engine()
    now = datetime.now(timezone.utc)

    ep_total = engine.episodes.count()
    co_total = engine.concepts.count()
    fa_total = engine.facts.count()
    bl_total = engine.beliefs.count()

    # Pre fetch concept metadata
    concept_metas = []
    if co_total > 0:
        concept_results = engine.concepts.collection.get(include=["metadatas"])
        concept_metas = concept_results["metadatas"]

    # Pre fetch fact metadata
    fact_rows = []
    if fa_total > 0:
        fact_rows = engine.facts.conn.execute("SELECT * FROM facts").fetchall()

    steps = []
    for day in range(0, days + 1, step):
        future = now + timedelta(days=day)

        ep_active = len(engine.episodes.list_active(now=future))

        co_active = 0
        for meta in concept_metas:
            conf = compute_confidence(
                initial_confidence=meta["initial_confidence"],
                created_at=datetime.fromisoformat(meta["timestamp"]),
                half_life=timedelta(days=meta["half_life_days"]),
                reinforcement_count=meta.get("reinforcement_count", 0),
                now=future,
            )
            if conf >= 0.05:
                co_active += 1

        fa_active = 0
        for row in fact_rows:
            conf = compute_confidence(
                initial_confidence=row["initial_confidence"],
                created_at=datetime.fromisoformat(row["timestamp"]),
                half_life=timedelta(days=row["half_life_days"]),
                reinforcement_count=row["reinforcement_count"],
                now=future,
            )
            if conf >= 0.05:
                fa_active += 1

        bl_active = len(engine.beliefs.list_beliefs(now=future))

        steps.append(SimulateStep(
            day=day, episodes=ep_active, concepts=co_active,
            facts=fa_active, beliefs=bl_active,
        ))

    return SimulateResponse(
        steps=steps,
        total_episodes=ep_total, total_concepts=co_total,
        total_facts=fa_total, total_beliefs=bl_total,
    )


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


# Serve frontend index.html for all non-API routes (SPA fallback)
if _ui_dist.exists():
    from starlette.responses import FileResponse

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        file_path = _ui_dist / path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_ui_dist / "index.html"))
