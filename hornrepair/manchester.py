"""
Manchester-syntax text for class expressions and axioms, read straight from the Turtle graph.

Used by the demo to show an ontology's axioms as a reader would write them
(`Author SubClassOf writes some Book`) and by the identity normaliser to name the axiom it
refuses. Only the constructs that can occur in the witnesses are rendered.
"""

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from hornrepair.extract import AXIOM_PREDICATES, TYPED_AXIOMS, local

CARDINALITY_WORDS = {
    OWL.minQualifiedCardinality: "min", OWL.minCardinality: "min",
    OWL.maxQualifiedCardinality: "max", OWL.maxCardinality: "max",
    OWL.qualifiedCardinality: "exactly", OWL.cardinality: "exactly",
}
AXIOM_WORDS = {
    RDFS.subClassOf: "SubClassOf", RDFS.subPropertyOf: "SubPropertyOf", OWL.disjointWith: "DisjointWith",
    OWL.equivalentClass: "EquivalentTo", OWL.equivalentProperty: "EquivalentTo", RDFS.domain: "Domain",
    RDFS.range: "Range", OWL.inverseOf: "InverseOf",
}


def list_items(g: Graph, head: object) -> list[object]:
    """The members of an RDF list, or [] when there is no list."""
    return list(g.items(head)) if head is not None else []


def expr(g: Graph, node: object) -> str:
    """A class expression in Manchester syntax, with local names for IRIs."""
    if isinstance(node, URIRef):
        return local(node)
    if isinstance(node, Literal):
        return str(node)
    if not isinstance(node, BNode):
        return "?"
    for predicate, word in ((OWL.intersectionOf, " and "), (OWL.unionOf, " or ")):
        if g.value(node, predicate) is not None:
            return "(" + word.join(expr(g, member) for member in list_items(g, g.value(node, predicate))) + ")"
    if g.value(node, OWL.complementOf) is not None:
        return "not " + expr(g, g.value(node, OWL.complementOf))
    if g.value(node, OWL.oneOf) is not None:
        return "{" + ", ".join(expr(g, member) for member in list_items(g, g.value(node, OWL.oneOf))) + "}"
    prop = expr(g, g.value(node, OWL.onProperty))
    for predicate, word in ((OWL.someValuesFrom, "some"), (OWL.allValuesFrom, "only"), (OWL.hasValue, "value")):
        if g.value(node, predicate) is not None:
            return f"{prop} {word} {expr(g, g.value(node, predicate))}"
    for predicate, word in CARDINALITY_WORDS.items():
        if g.value(node, predicate) is not None:
            filler = g.value(node, OWL.onClass)
            qualifier = f" {expr(g, filler)}" if filler is not None else ""
            return f"{prop} {word} {g.value(node, predicate)}{qualifier}"
    return "<unsupported expression>"


def axioms(g: Graph) -> list[str]:
    """Every logical axiom of `g`, one Manchester-style line each, sorted."""
    lines = []
    for predicate in AXIOM_PREDICATES:
        for subject, obj in g.subject_objects(predicate):
            if predicate == OWL.inverseOf and isinstance(subject, BNode):
                continue  # a property expression inside a restriction, not an axiom
            lines.append(f"{expr(g, subject)} {AXIOM_WORDS.get(predicate, local(predicate))} {expr(g, obj)}")
    for axiom_type in TYPED_AXIOMS:
        word = local(axiom_type).replace("Property", "")  # FunctionalProperty -> Functional
        lines += [f"{word}: {expr(g, subject)}" for subject in g.subjects(RDF.type, axiom_type)]
    return sorted(lines)
