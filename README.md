# Engram

**A local-first AI memory system with probabilistic decay.**

Engram is not another database. It's a memory engine that works the way biological memory does. Raw experiences compress into understanding, understanding distills into wisdom, and everything fades unless it matters.

## Why

For 50+ years, databases have stored data as permanent, binary truth. A row exists or it doesn't. But real memory doesn't work that way.

Current AI memory solutions (Mem0, Zep, Letta) are smart, but they're still **orchestration layers on top of 1970s paradigms**. They bolt vector search and knowledge graphs onto traditional stores and call it memory. Underneath, it's still static rows and rigid triples.

Engram takes a different approach:

1. **Memories fade.** Every memory has a half-life. Unused knowledge naturally decays. This isn't a bug. It's how you avoid drowning in stale data.
2. **Contradictions resolve themselves.** Say "I love Java" today and "I hate Java" next month. Engram doesn't just overwrite. The newer fact gains weight while the older one decays faster.
3. **Understanding deepens over time.** Raw text compresses into concepts, concepts distill into principles. Three layers, like sediment forming rock.

## What

Engram has three memory layers, each with different compression and decay rates:

```
L1: Episodes (raw text)      half-life: 7 days
        | synthesize
        v
L2: Concepts (compressed)    half-life: 90 days
        | distill
        v
L3: Beliefs (principles)     half-life: 365 days
        |
        +-- connected by graph edges (supports, contradicts, reminds_of)
```

**Retrieval** blends three signals into one ranked result:

1. **Vector similarity (60%)** semantic meaning via embeddings
2. **Graph traversal (25%)** structural relationships between beliefs
3. **Recency boost (15%)** newer memories score higher

**Everything runs locally.** No API keys, no cloud, no data leaves your machine.

| Component | Technology |
|---|---|
| LLM | Ollama (llama3.2 or any local model) |
| Embeddings | MiniLM-L6-v2 (via ChromaDB, local ONNX) |
| Vector store | ChromaDB (embedded, local files) |
| Graph store | NetworkX + JSON |
| Episode store | SQLite |

## How

### Install

```bash
# Prerequisites
brew install ollama
ollama pull llama3.2

# Install Engram
git clone <repo-url> && cd engram
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

### CLI

```bash
# Ingest raw memories
engram ingest "I prefer Python for backend development"
engram ingest "Rust impresses me with its memory safety"
engram ingest "Simple composable tools beat monolithic frameworks"

# Synthesize: compress episodes into concepts and beliefs
engram synthesize
#   Episodes processed:        3
#   Concepts created:          2
#   Concepts merged (dedup):   0
#   Beliefs created:           1
#   Edges created:             1
#   Contradictions resolved:   0

# Recall with hybrid retrieval
engram recall "programming preferences"
#   [1] [L2:CO] (score: 0.272) Python preferred for readability
#   [2] [L2:CO] (score: 0.247) User prefers Rust for memory safety
#   [3] [L1:EP] (score: 0.091) I prefer Python for backend development

# See memory stats
engram status
#   L1 Episodes:  3
#   L2 Concepts:  2
#   L3 Beliefs:   1
#   Graph Edges:  1

# Simulate decay over time
engram simulate --days 365
#   Day   0: Episodes 3/3 (100%) ████████████
#   Day  60: Episodes 0/3 (  0%)
#   Day 360: Concepts 2/3 ( 66%) ████████

# Visualize the belief graph
engram graph  # opens interactive HTML in browser

# Interactive chat with live memory
engram chat
#   you> I've been learning Haskell lately
#     memorized (4 episodes)
#   you> /recall programming
#     [1] [CO] 0.31 | User explores functional programming languages
#   you> /synthesize
#     +2 concepts, +1 beliefs, +1 edges
#   you> /quit

# REST API
engram serve  # starts on http://127.0.0.1:8420
```

### API Endpoints

```
POST /ingest            store raw text as episode
POST /recall            hybrid retrieval across all layers
POST /synthesize        run the compression pipeline
GET  /status            memory statistics
DELETE /forget/{id}     remove a specific memory
GET  /health            health check
```

### Python SDK

```python
from engram.engine import Engram

engine = Engram()
engine.initialize()

# Ingest
engine.ingest("User prefers functional programming")

# Synthesize (compresses episodes into concepts and beliefs)
result = engine.synthesize_sync()

# Recall
results = engine.recall("programming style")
for r in results:
    print(f"[{r.layer}] {r.score:.3f} | {r.content}")

engine.close()
```

### Streaming Session (for integration)

```python
from engram.streaming import EngramSession

session = EngramSession(synthesis_interval=300)  # auto synthesize every 5 min
session.start()

session.user("I like composable tools")
session.assistant("Noted, you prefer Unix philosophy")

results = session.recall("design preferences")

session.stop()
```

### Configuration

All settings via environment variables (prefix `ENGRAM_`):

```bash
ENGRAM_OLLAMA_MODEL=llama3.2        # any Ollama model
ENGRAM_OLLAMA_HOST=http://localhost:11434
ENGRAM_DATA_DIR=~/.engram           # where all data lives
ENGRAM_EPISODE_HALF_LIFE_DAYS=7     # L1 decay rate
ENGRAM_CONCEPT_HALF_LIFE_DAYS=90    # L2 decay rate
ENGRAM_BELIEF_HALF_LIFE_DAYS=365    # L3 decay rate
ENGRAM_VECTOR_WEIGHT=0.60           # retrieval blend weights
ENGRAM_GRAPH_WEIGHT=0.25
ENGRAM_RECENCY_WEIGHT=0.15
ENGRAM_MIN_CONFIDENCE=0.05          # garbage collection threshold
```

## Architecture

```
┌─────────────────────────────────────┐
│            engram recall            │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│         Retrieval Mixer             │
│  vector similarity ····· 60%        │
│  graph traversal ······· 25%        │
│  recency boost ········· 15%        │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│       Three Layer Memory            │
│                                     │
│  L1 Episodes ··· SQLite + ChromaDB  │
│  L2 Concepts ··· ChromaDB vectors   │
│  L3 Beliefs ···· NetworkX graph     │
│                                     │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│      Synthesis Pipeline             │
│                                     │
│  Extractor ···· episodes > concepts │
│  Distiller ···· concepts > beliefs  │
│  Deduplicator · merge near dupes    │
│  Contradiction · detect & resolve   │
│  Decay ········ probabilistic fade  │
│                                     │
│  Powered by Ollama (local LLM)      │
└─────────────────────────────────────┘
```

## Key Ideas

**Probabilistic Decay**
```
confidence(t) = C0 x 0.5^(elapsed / half_life) x reinforcement_boost
```
Each reinforcement (access) extends the effective half life by 20%. Memories you use get stronger. Memories you ignore fade away.

**Three Layer Abstraction**

1. **Episodes** are what you said. They're exact, ephemeral, and decay fast.
2. **Concepts** are what you meant. Extracted by the LLM, they carry vector embeddings.
3. **Beliefs** are what you are. Abstract principles that persist for years.

**Contradiction Resolution**

When conflicting facts are detected, the newer one gets reinforced and the older one's half life is halved. No manual cleanup needed.

**Auto Reinforcement**

The top 3 results of every recall get their reinforcement count bumped. Useful memories naturally outlive useless ones.

## License

MIT
