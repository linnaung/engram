"""Engram CLI — terminal interface for the memory engine."""

from __future__ import annotations

import json
import sys

import click

from engram.engine import Engram
from engram.core.config import get_config


def _get_engine() -> Engram:
    config = get_config()
    engine = Engram(config)
    engine.initialize()
    return engine


@click.group()
@click.version_option(package_name="engram")
def cli():
    """Engram — Temporal Concept Graph with Probabilistic Decay.

    A novel AI memory system with three layers:
    Episodes (raw) -> Concepts (compressed) -> Beliefs (wisdom)
    """


@cli.command()
@click.argument("text")
@click.option("--source", "-s", default="conversation", help="Memory source label")
def ingest(text: str, source: str):
    """Ingest raw text as an episodic memory."""
    engine = _get_engine()
    try:
        episode = engine.ingest(text, source=source)
        click.echo(f"Ingested episode {episode.id[:8]}...")
        click.echo(f"  Content: {episode.content[:80]}{'...' if len(episode.content) > 80 else ''}")
        click.echo(f"  Confidence: {episode.confidence:.2f} (half-life: {episode.half_life_days}d)")
    finally:
        engine.close()


@cli.command()
@click.argument("query")
@click.option("--top-k", "-k", default=5, help="Max results")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def recall(query: str, top_k: int, json_output: bool):
    """Recall memories using hybrid retrieval."""
    engine = _get_engine()
    try:
        results = engine.recall(query, top_k=top_k)

        if not results:
            click.echo("No memories found.")
            return

        if json_output:
            output = [
                {
                    "content": r.content,
                    "layer": r.layer,
                    "score": round(r.score, 4),
                    "confidence": round(r.confidence, 4),
                    "source_id": r.source_id,
                }
                for r in results
            ]
            click.echo(json.dumps(output, indent=2))
        else:
            for i, r in enumerate(results, 1):
                layer_badge = {"episode": "L1:EP", "concept": "L2:CO", "belief": "L3:BL"}
                badge = layer_badge.get(r.layer, r.layer.upper())
                click.echo(f"\n[{i}] [{badge}] (score: {r.score:.3f}, conf: {r.confidence:.3f})")
                click.echo(f"    {r.content}")
    finally:
        engine.close()


@cli.command()
def synthesize():
    """Run the synthesis loop: compress episodes -> concepts -> beliefs."""
    engine = _get_engine()
    try:
        click.echo("Running synthesis...")
        result = engine.synthesize_sync()
        click.echo(f"  Episodes processed:        {result['episodes_processed']}")
        click.echo(f"  Concepts created:          {result['concepts_created']}")
        click.echo(f"  Facts extracted:           {result.get('facts_created', 0)}")
        click.echo(f"  Fact contradictions:       {result.get('fact_contradictions', 0)}")
        click.echo(f"  Concepts merged (dedup):   {result.get('concepts_merged', 0)}")
        click.echo(f"  Beliefs created:           {result['beliefs_created']}")
        click.echo(f"  Edges created:             {result['edges_created']}")
        click.echo(f"  Contradictions resolved:   {result.get('contradictions_resolved', 0)}")
        click.echo(f"  Episodes garbage collected: {result['episodes_garbage_collected']}")
    finally:
        engine.close()


@cli.command()
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def status(json_output: bool):
    """Show memory statistics."""
    engine = _get_engine()
    try:
        stats = engine.status()

        if json_output:
            click.echo(json.dumps(stats, indent=2))
        else:
            click.echo("Engram Memory Status")
            click.echo("=" * 40)
            click.echo(f"  L1 Episodes:   {stats['episodes']}")
            click.echo(f"  L2 Concepts:   {stats['concepts']}")
            click.echo(f"  L2.5 Facts:    {stats['facts']}")
            click.echo(f"  L3 Beliefs:    {stats['beliefs']}")
            click.echo(f"  Graph Edges:   {stats['edges']}")
            click.echo(f"  Context:       {'loaded' if stats.get('context_loaded') else 'none'}")
            click.echo(f"  Data dir:      {stats['data_dir']}")
    finally:
        engine.close()


@cli.command()
@click.argument("memory_id")
def forget(memory_id: str):
    """Remove a specific memory by ID."""
    engine = _get_engine()
    try:
        if engine.forget(memory_id):
            click.echo(f"Forgotten: {memory_id}")
        else:
            click.echo(f"Memory not found: {memory_id}", err=True)
            sys.exit(1)
    finally:
        engine.close()


@cli.command()
@click.option("--synth-interval", default=300, help="Seconds between auto-synthesis (default: 300)")
def chat(synth_interval: int):
    """Interactive chat with live memory — talk, and Engram remembers.

    Type messages to ingest them. Use special commands:
      /recall <query>   - Search memories
      /status           - Show memory stats
      /synthesize       - Run synthesis now
      /quit             - Exit
    """
    from engram.streaming import EngramSession

    session = EngramSession(
        synthesis_interval=float(synth_interval),
        auto_synthesize=True,
    )
    session.start()

    click.echo("Engram Chat - your memory is always on")
    click.echo("=" * 45)
    click.echo("Type to add memories. Commands: /recall, /status, /synthesize, /quit")
    click.echo(f"Auto-synthesis every {synth_interval}s\n")

    try:
        while True:
            try:
                text = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not text:
                continue

            if text == "/quit":
                break

            if text == "/status":
                stats = session.status()
                click.echo(f"  Episodes: {stats['episodes']} | Concepts: {stats['concepts']} | Facts: {stats['facts']} | Beliefs: {stats['beliefs']} | Edges: {stats['edges']} | Turns: {stats['session_turns']}")
                continue

            if text == "/synthesize":
                click.echo("  Synthesizing...")
                result = session.synthesize_now()
                click.echo(f"  +{result['concepts_created']} concepts, +{result['beliefs_created']} beliefs, +{result['edges_created']} edges, ~{result.get('concepts_merged', 0)} merged, !{result.get('contradictions_resolved', 0)} contradictions")
                continue

            if text.startswith("/recall "):
                query = text[8:].strip()
                if not query:
                    click.echo("  Usage: /recall <query>")
                    continue
                results = session.recall(query, top_k=5)
                if not results:
                    click.echo("  No memories found.")
                else:
                    for i, r in enumerate(results, 1):
                        badge = {"episode": "EP", "concept": "CO", "belief": "BL"}.get(r.layer, "??")
                        click.echo(f"  [{i}] [{badge}] {r.score:.3f} | {r.content}")
                continue

            # Regular text — ingest as user message
            session.user(text)
            click.echo(f"  memorized ({session.status()['episodes']} episodes)")

    finally:
        click.echo("\nSaving memory state...")
        session.stop()
        click.echo("Session ended.")


@cli.command()
@click.option("--days", "-d", default=30, help="Days to simulate forward")
@click.option("--step", "-s", default=7, help="Days per step")
def simulate(days: int, step: int):
    """Simulate memory decay over time — see what survives.

    Shows how your memories fade over the specified period.
    """
    from datetime import timedelta

    engine = _get_engine()
    try:
        from engram.core.decay import compute_confidence
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)

        click.echo(f"Simulating {days} days of memory decay (step: {step}d)")
        click.echo("=" * 60)

        for day in range(0, days + 1, step):
            future = now + timedelta(days=day)

            ep_active = len(engine.episodes.list_active(now=future))
            ep_total = engine.episodes.count()

            # Count active concepts
            concept_results = engine.concepts.collection.get(include=["metadatas"])
            co_active = 0
            for meta in concept_results["metadatas"]:
                conf = compute_confidence(
                    initial_confidence=meta["initial_confidence"],
                    created_at=datetime.fromisoformat(meta["timestamp"]),
                    half_life=timedelta(days=meta["half_life_days"]),
                    reinforcement_count=meta.get("reinforcement_count", 0),
                    now=future,
                )
                if conf >= 0.05:
                    co_active += 1
            co_total = len(concept_results["ids"])

            bl_active = len(engine.beliefs.list_beliefs(now=future))
            bl_total = engine.beliefs.count()

            # Visual bar
            ep_pct = (ep_active / ep_total * 100) if ep_total > 0 else 0
            co_pct = (co_active / co_total * 100) if co_total > 0 else 0
            bl_pct = (bl_active / bl_total * 100) if bl_total > 0 else 0

            click.echo(f"\n  Day {day:3d}:")
            click.echo(f"    Episodes:  {ep_active:3d}/{ep_total} ({ep_pct:5.1f}%) {'#' * int(ep_pct / 5)}")
            click.echo(f"    Concepts:  {co_active:3d}/{co_total} ({co_pct:5.1f}%) {'#' * int(co_pct / 5)}")
            click.echo(f"    Beliefs:   {bl_active:3d}/{bl_total} ({bl_pct:5.1f}%) {'#' * int(bl_pct / 5)}")
    finally:
        engine.close()


@cli.command()
@click.option("--output", "-o", default=None, help="Output HTML file path")
def graph(output: str):
    """Visualize the belief graph as an interactive HTML page."""
    engine = _get_engine()
    try:
        beliefs = engine.beliefs.list_beliefs()
        if not beliefs:
            click.echo("No beliefs to visualize.")
            return

        edges_data = []
        for u, v, data in engine.beliefs.graph.edges(data=True):
            edges_data.append({
                "from": u[:8],
                "to": v[:8],
                "label": data.get("relation", "related"),
                "value": data.get("weight", 0.5),
            })

        nodes_data = []
        for b in beliefs:
            nodes_data.append({
                "id": b.id[:8],
                "label": b.principle[:50] + ("..." if len(b.principle) > 50 else ""),
                "title": f"{b.principle}\n\nConfidence: {b.confidence:.2f}\nHalf-life: {b.half_life_days}d",
                "value": b.confidence * 10,
            })

        html = _generate_graph_html(nodes_data, edges_data, engine.status())

        out_path = output or str(engine.config.data_dir / "graph.html")
        with open(out_path, "w") as f:
            f.write(html)
        click.echo(f"Graph saved to: {out_path}")
        click.echo(f"  {len(nodes_data)} nodes, {len(edges_data)} edges")

        # Try to open in browser
        try:
            import webbrowser
            webbrowser.open(f"file://{out_path}")
        except Exception:
            pass

    finally:
        engine.close()


def _generate_graph_html(nodes: list, edges: list, stats: dict) -> str:
    """Generate a standalone HTML page with vis.js graph visualization."""
    import json as _json

    nodes_json = _json.dumps(nodes)
    edges_json = _json.dumps(edges)

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Engram - Belief Graph</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0a; color: #e0e0e0; }}
        #header {{ padding: 20px 30px; background: #111; border-bottom: 1px solid #333; display: flex; justify-content: space-between; align-items: center; }}
        #header h1 {{ font-size: 24px; font-weight: 300; }}
        #header h1 span {{ color: #7c5cff; font-weight: 600; }}
        #stats {{ display: flex; gap: 20px; font-size: 13px; color: #888; }}
        #stats .stat {{ text-align: center; }}
        #stats .stat .num {{ font-size: 22px; color: #e0e0e0; font-weight: 600; }}
        #graph {{ width: 100%; height: calc(100vh - 80px); }}
    </style>
</head>
<body>
    <div id="header">
        <h1><span>Engram</span> Belief Graph</h1>
        <div id="stats">
            <div class="stat"><div class="num">{stats.get('episodes', 0)}</div>Episodes</div>
            <div class="stat"><div class="num">{stats.get('concepts', 0)}</div>Concepts</div>
            <div class="stat"><div class="num">{stats.get('beliefs', 0)}</div>Beliefs</div>
            <div class="stat"><div class="num">{stats.get('edges', 0)}</div>Edges</div>
        </div>
    </div>
    <div id="graph"></div>
    <script>
        var nodes = new vis.DataSet({nodes_json});
        var edges = new vis.DataSet({edges_json});
        var container = document.getElementById('graph');
        var data = {{ nodes: nodes, edges: edges }};
        var options = {{
            nodes: {{
                shape: 'dot',
                font: {{ color: '#e0e0e0', size: 14 }},
                color: {{ background: '#7c5cff', border: '#5a3fd4', highlight: {{ background: '#9d85ff', border: '#7c5cff' }} }},
                scaling: {{ min: 15, max: 40 }},
            }},
            edges: {{
                color: {{ color: '#444', highlight: '#7c5cff' }},
                font: {{ color: '#888', size: 11, strokeWidth: 0 }},
                arrows: {{ to: {{ enabled: true, scaleFactor: 0.8 }} }},
                smooth: {{ type: 'continuous' }},
            }},
            physics: {{
                barnesHut: {{ gravitationalConstant: -3000, centralGravity: 0.1, springLength: 200 }},
                stabilization: {{ iterations: 150 }},
            }},
            background: '#0a0a0a',
        }};
        new vis.Network(container, data, options);
    </script>
</body>
</html>"""


@cli.command("context")
@click.argument("ontology_path")
def load_context(ontology_path: str):
    """Load a domain ontology from a JSON file.

    Example: engram context examples/ontology_lifescience.json
    """
    from engram.context.loader import load_ontology

    ctx = load_ontology(ontology_path)
    click.echo(f"Loaded ontology from: {ontology_path}")
    click.echo(f"  Types:      {len(ctx.list_types())}")
    click.echo(f"  Predicates: {len(ctx.list_predicates())}")
    click.echo(f"  Types:      {', '.join(ctx.list_types()[:10])}")
    click.echo(f"  Predicates: {', '.join(ctx.list_predicates()[:10])}")
    click.echo(f"\nTo use during synthesis, set:")
    click.echo(f"  export ENGRAM_CONTEXT_FILE={ontology_path}")


@cli.group("facts")
def facts_group():
    """Query and inspect extracted facts (L2.5 structured triples)."""


@facts_group.command("list")
@click.option("--limit", "-n", default=20, help="Max facts to show")
def facts_list(limit: int):
    """List all active facts."""
    engine = _get_engine()
    try:
        all_facts = engine.facts.query(min_confidence=0.05)
        if not all_facts:
            click.echo("No facts extracted yet. Run 'engram synthesize' first.")
            return

        for i, f in enumerate(all_facts[:limit], 1):
            type_info = ""
            if f.subject_type or f.object_type:
                type_info = f" ({f.subject_type} > {f.object_type})"
            click.echo(f"  [{i}] {f.subject} {f.predicate} {f.object}{type_info}  (conf: {f.confidence:.2f})")

        if len(all_facts) > limit:
            click.echo(f"  ... and {len(all_facts) - limit} more")
    finally:
        engine.close()


@facts_group.command("query")
@click.argument("entity")
def facts_query(entity: str):
    """Query facts by entity name (searches subject and object)."""
    engine = _get_engine()
    try:
        as_subject = engine.facts.query(subject=entity)
        as_object = engine.facts.query(object=entity)

        all_facts = {f.id: f for f in as_subject + as_object}

        if not all_facts:
            click.echo(f"No facts found for '{entity}'.")
            return

        click.echo(f"Facts about '{entity}':")
        for f in all_facts.values():
            type_info = ""
            if f.subject_type or f.object_type:
                type_info = f" ({f.subject_type} > {f.object_type})"
            click.echo(f"  {f.subject} {f.predicate} {f.object}{type_info}  (conf: {f.confidence:.2f})")
    finally:
        engine.close()


@cli.command()
def serve():
    """Start the Engram REST API server."""
    import uvicorn
    from engram.core.config import get_config

    config = get_config()
    click.echo(f"Starting Engram API on {config.api_host}:{config.api_port}")
    uvicorn.run(
        "engram.api.server:app",
        host=config.api_host,
        port=config.api_port,
        reload=False,
    )


if __name__ == "__main__":
    cli()
