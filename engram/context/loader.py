"""Load domain ontologies from Turtle (.ttl) or JSON-LD (.jsonld) files.

Uses rdflib to parse standard RDF formats. Extracts:
  - Type hierarchy from rdfs:subClassOf triples
  - Entities from rdf:type triples
  - Entity labels/aliases from rdfs:label and skos:altLabel
  - Predicate domain/range from rdfs:domain and rdfs:range
"""

from __future__ import annotations

from pathlib import Path

from rdflib import Graph, Namespace, RDF, RDFS, OWL, XSD, Literal
from rdflib.namespace import SKOS, DCTERMS

from engram.context.provider import SimpleContext

# Engram namespace for custom ontology properties
ENGRAM = Namespace("http://engram.dev/ontology#")


def load_ontology(path: str | Path) -> SimpleContext:
    """Load an ontology from Turtle (.ttl) or JSON-LD (.jsonld) file.

    Supported formats (detected by file extension):
      .ttl      Turtle (RDF)
      .jsonld   JSON-LD

    The loader extracts:
      - Classes as types, with rdfs:subClassOf for hierarchy
      - Properties as predicates, with rdfs:domain and rdfs:range
      - Named individuals as entities, with rdfs:label and skos:altLabel
    """
    path = Path(path)
    fmt = _detect_format(path)

    g = Graph()

    if fmt == "turtle":
        # Inject common prefixes that ontology files often assume but don't declare
        common_prefixes = (
            '@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n'
            '@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n'
        )
        content = path.read_text(encoding="utf-8")
        # Only inject if prefix is missing
        if "@prefix xsd:" not in content:
            content = common_prefixes + content
        g.parse(data=content, format=fmt)
    else:
        g.parse(str(path), format=fmt)

    ctx = SimpleContext()

    _extract_types(g, ctx)
    _extract_predicates(g, ctx)
    _extract_entities(g, ctx)

    return ctx


def _detect_format(path: Path) -> str:
    """Detect RDF serialization format from file extension."""
    suffix = path.suffix.lower()
    formats = {
        ".ttl": "turtle",
        ".jsonld": "json-ld",
        ".json": "json-ld",  # assume JSON-LD for .json files
    }
    fmt = formats.get(suffix)
    if fmt is None:
        raise ValueError(
            f"Unsupported ontology format: {suffix}. "
            f"Use .ttl (Turtle) or .jsonld (JSON-LD)."
        )
    return fmt


def _local_name(uri) -> str:
    """Extract the local name from a URI (after # or last /)."""
    s = str(uri)
    if "#" in s:
        return s.split("#")[-1]
    return s.rsplit("/", 1)[-1]


def _extract_types(g: Graph, ctx: SimpleContext) -> None:
    """Extract OWL/RDFS classes as types with hierarchy."""
    # Find all classes (owl:Class and rdfs:Class)
    classes = set()
    for s in g.subjects(RDF.type, OWL.Class):
        classes.add(s)
    for s in g.subjects(RDF.type, RDFS.Class):
        classes.add(s)

    # Register types
    for cls in classes:
        name = _local_name(cls)
        ctx.add_type(name, parent=None)

    # Build hierarchy from rdfs:subClassOf
    for child, _, parent in g.triples((None, RDFS.subClassOf, None)):
        child_name = _local_name(child)
        parent_name = _local_name(parent)
        # Ensure both exist
        if child_name not in ctx._types:
            ctx.add_type(child_name)
        ctx._types[child_name] = parent_name
        if parent_name not in ctx._types:
            ctx.add_type(parent_name)


def _extract_predicates(g: Graph, ctx: SimpleContext) -> None:
    """Extract OWL/RDF properties as predicates with domain/range."""
    props = set()
    for s in g.subjects(RDF.type, OWL.ObjectProperty):
        props.add(s)
    for s in g.subjects(RDF.type, RDF.Property):
        props.add(s)

    for prop in props:
        name = _local_name(prop)

        domain = "Entity"
        range_type = "Entity"

        for _, _, d in g.triples((prop, RDFS.domain, None)):
            domain = _local_name(d)
        for _, _, r in g.triples((prop, RDFS.range, None)):
            range_type = _local_name(r)

        ctx.add_predicate(name, domain=domain, range_type=range_type)


def _extract_entities(g: Graph, ctx: SimpleContext) -> None:
    """Extract named individuals as entities with labels and aliases."""
    individuals = set()
    for s in g.subjects(RDF.type, OWL.NamedIndividual):
        individuals.add(s)

    # Also find instances of any domain class (not just NamedIndividual)
    for s, _, o in g.triples((None, RDF.type, None)):
        o_name = _local_name(o)
        if o_name in ctx._types and s not in individuals:
            individuals.add(s)

    for ind in individuals:
        name = _local_name(ind)

        # Determine type
        entity_type = "Entity"
        for _, _, t in g.triples((ind, RDF.type, None)):
            t_name = _local_name(t)
            if t_name in ctx._types:
                entity_type = t_name
                break

        # Collect aliases from rdfs:label and skos:altLabel
        aliases = []
        for _, _, label in g.triples((ind, RDFS.label, None)):
            if isinstance(label, Literal):
                label_str = str(label)
                if label_str != name:
                    aliases.append(label_str)

        for _, _, alt in g.triples((ind, SKOS.altLabel, None)):
            if isinstance(alt, Literal):
                aliases.append(str(alt))

        ctx.add_entity(name, entity_type, aliases)
