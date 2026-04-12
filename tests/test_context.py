"""Tests for the context provider and ontology loader."""

import pytest

from engram.context.provider import SimpleContext
from engram.context.loader import load_ontology


@pytest.fixture
def bio_context():
    ctx = SimpleContext()
    ctx.add_type("Entity")
    ctx.add_type("Molecule", parent="Entity")
    ctx.add_type("Protein", parent="Molecule")
    ctx.add_type("Gene", parent="Molecule")
    ctx.add_type("Drug", parent="Molecule")
    ctx.add_type("Disease", parent="Entity")

    ctx.add_predicate("inhibits", domain="Molecule", range_type="Molecule")
    ctx.add_predicate("treats", domain="Drug", range_type="Disease")
    ctx.add_predicate("binds_to", domain="Molecule", range_type="Molecule")

    ctx.add_entity("p53", "Protein", aliases=["TP53", "tumor protein p53"])
    ctx.add_entity("MDM2", "Gene", aliases=["HDM2"])
    ctx.add_entity("imatinib", "Drug", aliases=["Gleevec"])
    ctx.add_entity("leukemia", "Disease", aliases=["CML"])

    return ctx


class TestSimpleContext:
    def test_resolve_canonical(self, bio_context):
        entity = bio_context.resolve_entity("p53")
        assert entity is not None
        assert entity.canonical == "p53"
        assert entity.type == "Protein"

    def test_resolve_alias(self, bio_context):
        entity = bio_context.resolve_entity("TP53")
        assert entity is not None
        assert entity.canonical == "p53"

    def test_resolve_case_insensitive(self, bio_context):
        entity = bio_context.resolve_entity("tp53")
        assert entity is not None
        assert entity.canonical == "p53"

    def test_resolve_unknown(self, bio_context):
        assert bio_context.resolve_entity("unknown_protein") is None

    def test_is_subtype_direct(self, bio_context):
        assert bio_context.is_subtype("Protein", "Molecule") is True

    def test_is_subtype_transitive(self, bio_context):
        assert bio_context.is_subtype("Protein", "Entity") is True

    def test_is_subtype_self(self, bio_context):
        assert bio_context.is_subtype("Protein", "Protein") is True

    def test_is_subtype_false(self, bio_context):
        assert bio_context.is_subtype("Disease", "Molecule") is False

    def test_validate_triple_valid(self, bio_context):
        # Protein inhibits Gene (both are Molecules)
        assert bio_context.validate_triple("Protein", "inhibits", "Gene") is True

    def test_validate_triple_invalid(self, bio_context):
        # Disease cannot "treats" Disease (treats requires Drug domain)
        assert bio_context.validate_triple("Disease", "treats", "Disease") is False

    def test_validate_triple_unknown_predicate(self, bio_context):
        # Unknown predicates are allowed by default
        assert bio_context.validate_triple("Protein", "unknown_relation", "Gene") is True

    def test_get_type_hierarchy(self, bio_context):
        h = bio_context.get_type_hierarchy("Protein")
        assert h == ["Protein", "Molecule", "Entity"]

    def test_list_types(self, bio_context):
        types = bio_context.list_types()
        assert "Protein" in types
        assert "Gene" in types
        assert "Disease" in types

    def test_list_predicates(self, bio_context):
        preds = bio_context.list_predicates()
        assert "inhibits" in preds
        assert "treats" in preds


class TestOntologyLoader:
    def test_load_turtle(self, tmp_path):
        ttl = """\
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix eng: <http://engram.dev/ontology#> .

eng:Entity a owl:Class .
eng:Language a owl:Class ; rdfs:subClassOf eng:Entity .

eng:prefers a owl:ObjectProperty ;
    rdfs:domain eng:Entity ;
    rdfs:range eng:Entity .

eng:Python a owl:NamedIndividual, eng:Language ;
    rdfs:label "Python" ;
    skos:altLabel "python3" .
"""
        path = tmp_path / "test.ttl"
        path.write_text(ttl)

        ctx = load_ontology(path)

        assert "Language" in ctx.list_types()
        assert "prefers" in ctx.list_predicates()

        entity = ctx.resolve_entity("python3")
        assert entity is not None
        assert entity.canonical == "Python"
        assert entity.type == "Language"

    def test_load_jsonld(self, tmp_path):
        jsonld = """{
  "@context": {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "eng": "http://engram.dev/ontology#"
  },
  "@graph": [
    {"@id": "eng:Entity", "@type": "owl:Class"},
    {"@id": "eng:Tool", "@type": "owl:Class", "rdfs:subClassOf": {"@id": "eng:Entity"}},
    {"@id": "eng:uses", "@type": "owl:ObjectProperty", "rdfs:domain": {"@id": "eng:Entity"}, "rdfs:range": {"@id": "eng:Tool"}},
    {"@id": "eng:Rust", "@type": ["owl:NamedIndividual", "eng:Tool"], "rdfs:label": "Rust", "skos:altLabel": "rust-lang"}
  ]
}"""
        path = tmp_path / "test.jsonld"
        path.write_text(jsonld)

        ctx = load_ontology(path)

        assert "Tool" in ctx.list_types()
        assert ctx.is_subtype("Tool", "Entity") is True

        entity = ctx.resolve_entity("rust-lang")
        assert entity is not None
        assert entity.canonical == "Rust"

    def test_load_lifescience_example(self):
        """Test loading the shipped life science Turtle ontology."""
        from pathlib import Path
        example = Path(__file__).parent.parent / "examples" / "ontology_lifescience.ttl"
        if not example.exists():
            pytest.skip("Example ontology not found")

        ctx = load_ontology(example)
        assert len(ctx.list_types()) > 5
        assert len(ctx.list_predicates()) > 5

        p53 = ctx.resolve_entity("TP53")
        assert p53 is not None
        assert p53.canonical == "p53"
        assert p53.type == "Protein"

        assert ctx.is_subtype("Protein", "Molecule") is True
        assert ctx.is_subtype("Drug", "SmallMolecule") is True
        assert ctx.validate_triple("Protein", "inhibits", "Gene") is True
