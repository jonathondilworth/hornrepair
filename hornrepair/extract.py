"""
Stage 3 of the pipeline: two Turtle ontologies plus the alignment -> Horn fact files for Soufflé.

Every logical axiom of each ontology either becomes one or more facts of the relations
below, or is dropped and counted under a label that names its shape. Dropping is sound
(fewer facts can only mean fewer entailments); approximating an unsupported axiom by a
similar supported one would not be, so it is never done.

The relations, with the argument roles the rule file declares (C class, P property, N number):

    sub(C, C)   subp(P, P)   disj(C, C)          named subsumption, sub-property, disjointness
    cls(C)      prop(P)                          every class and object property that occurs anywhere
    some(C, P, C)          only(C, P, C)         a ⊑ ∃r.F,   a ⊑ ∀r.F       restriction on the right of ⊑
    atleast(C, P, N, C)    atmost(C, P, N, C)    a ⊑ ≥n r.F, a ⊑ ≤n r.F
    someLHS(P, C, C)       onlyLHS(P, C, C)      ∃r.F ⊑ g,   ∀r.F ⊑ g       restriction on the left of ⊑
    atleastLHS(P, N, C, C) atmostLHS(P, N, C, C) ≥n r.F ⊑ g, ≤n r.F ⊑ g     (definitions, general inclusions)
    Func(P)     Range(P, C)  Domain(P, C)        global property axioms; the rule file moves them onto T

One tab-separated `<relation>.facts` file is written per relation, empty ones included,
because Soufflé refuses to run when an input file is missing. The mapping facts are written
last and also returned by mapping id, so that blame.py can remove one mapping at a time.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Iterator, NamedTuple

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from hornrepair.matcher import Mapping

Fact = tuple[str, ...]  # (relation, argument, ...): IRIs as full strings, numbers as digit strings


##
# The extract step essentially transforms the TBox axioms into datalog facts.
# For instance, we declare `.decl sub(c, d)` and `.decl cls(c)` in the rules, with `cls(TOP).` `sub(c, TOP) :- cls(c).`
# so we will need to "extract" the logical axioms from the ontologies, such as:
#
# :Book a owl:Class ;
#   rdfs:label "Book" ;
#   rdfs:subClassOf :Document .
#
# which says that a "Book" is a class, and that a "Book" is a subclass of "Document".
# Such that they are usable as inputs to our inference engine. The `.facts` files are just URIs.
# So for `cls.facts` and `sub.facts` we would get:
#
# http://example.org/o1#Book     (cls.facts)
# http://example.org/o1#Document (cls.facts)
#
# http://example.org/o1#Book    http://example.org/o1#Document (sub.facts)
#
# In essence, each logical axiom is observed and either becomes a fact (as above) or is dropped (if it does not match a shape we have defiend).
# Note that for Domain axioms, for instance, their restrictions are on the LEFT HAND SIDE (LHS)! This is why we have the LHS shapes.
# The mappings must also be extracted; they are extracted last. 
# Recall that equivalance becomes two directed inclusions, so the mappings become `sub` or `subp` facts.
# Dropping axioms is sound, since fewer facts means fewer conclusions (monotonicity).
##


THING = str(OWL.Thing)

# Argument roles of every relation, in the order the rule file declares them.
# C = class IRI, P = object-property IRI, N = non-negative integer.
SIGNATURES: dict[str, str] = {
    "sub": "CC", "subp": "PP", "disj": "CC",
    "cls": "C", "prop": "P",
    "some": "CPC", "only": "CPC", "atleast": "CPNC", "atmost": "CPNC",
    "someLHS": "PCC", "onlyLHS": "PCC", "atleastLHS": "PNCC", "atmostLHS": "PNCC",
    "Func": "P", "Range": "PC", "Domain": "PC",
}
RELATIONS = tuple(SIGNATURES)

# A restriction on the left of ⊑ is recorded in the *LHS twin of its right-hand relation.
LHS_OF = {"some": "someLHS", "only": "onlyLHS", "atleast": "atleastLHS", "atmost": "atmostLHS"}


# restrictions

class Restriction(NamedTuple):
    """An OWL restriction blank node whose property and filler are both named."""
    kind: str          # some | only | atleast | atmost | exact
    property: str
    filler: str        # owl:Thing for an unqualified cardinality
    bound: int | None  # the n of a cardinality restriction; None for some / only


# Turtle predicate of a cardinality restriction -> (kind, whether the filler is given by owl:onClass)
CARDINALITY_PREDICATES = {
    OWL.minQualifiedCardinality: ("atleast", True),
    OWL.maxQualifiedCardinality: ("atmost", True),
    OWL.qualifiedCardinality: ("exact", True),
    OWL.minCardinality: ("atleast", False),
    OWL.maxCardinality: ("atmost", False),
    OWL.cardinality: ("exact", False),
}

# Every predicate that identifies what a class-expression blank node is; used to name dropped shapes.
RESTRICTION_KEYS = (
    OWL.someValuesFrom, OWL.allValuesFrom, *CARDINALITY_PREDICATES, OWL.hasValue, OWL.hasSelf,
    OWL.intersectionOf, OWL.unionOf, OWL.complementOf, OWL.oneOf,
)



def parse_restriction(g: Graph, node: BNode) -> Restriction | None:
    """The restriction a blank node encodes, or None when its property or filler is not a named IRI."""
    prop = g.value(node, OWL.onProperty)
    if not isinstance(prop, URIRef):
        return None
    for predicate, kind in ((OWL.someValuesFrom, "some"), (OWL.allValuesFrom, "only")):
        filler = g.value(node, predicate)
        if isinstance(filler, URIRef):
            return Restriction(kind, str(prop), str(filler), None)
    for predicate, (kind, qualified) in CARDINALITY_PREDICATES.items():
        literal = g.value(node, predicate)
        bound = literal.toPython() if isinstance(literal, Literal) else None
        filler = g.value(node, OWL.onClass) if qualified else OWL.Thing
        if isinstance(bound, int) and bound >= 0 and isinstance(filler, URIRef):
            return Restriction(kind, str(prop), str(filler), bound)
    return None



def right_hand_facts(a: str, r: Restriction) -> list[Fact]:
    """The facts for `a ⊑ R`. An exact cardinality is a lower and an upper bound at once."""
    if r.kind in ("some", "only"):
        return [(r.kind, a, r.property, r.filler)]
    kinds = ("atleast", "atmost") if r.kind == "exact" else (r.kind,)
    return [(kind, a, r.property, str(r.bound), r.filler) for kind in kinds]



def left_hand_facts(r: Restriction, g: str) -> list[Fact] | None:
    """The facts for `R ⊑ g`, or None for an exact cardinality: `=n r.F ⊑ g` entails neither half."""
    if r.kind == "exact":
        return None
    if r.kind in ("some", "only"):
        return [(LHS_OF[r.kind], r.property, r.filler, g)]
    return [(LHS_OF[r.kind], r.property, str(r.bound), r.filler, g)]



# axioms

# Predicates whose triples state a logical axiom (annotation predicates such as rdfs:label do not).
AXIOM_PREDICATES = {
    RDFS.subClassOf, RDFS.subPropertyOf, OWL.disjointWith, OWL.equivalentClass, OWL.equivalentProperty,
    OWL.inverseOf, RDFS.domain, RDFS.range, OWL.propertyChainAxiom, OWL.disjointUnionOf,
    OWL.propertyDisjointWith,
}

# rdf:type objects that are logical axioms in their own right.
TYPED_AXIOMS = {
    OWL.FunctionalProperty, OWL.InverseFunctionalProperty, OWL.TransitiveProperty,
    OWL.SymmetricProperty, OWL.AsymmetricProperty, OWL.ReflexiveProperty, OWL.IrreflexiveProperty,
    OWL.AllDisjointClasses, OWL.AllDisjointProperties,
}

# Axioms between two named entities that map straight onto a relation.
NAMED_AXIOMS = {RDFS.subClassOf: "sub", RDFS.subPropertyOf: "subp", OWL.disjointWith: "disj"}



def local(term: object) -> str:
    """The local name of an IRI: everything after the last '#' or '/'."""
    return re.split(r"[#/]", str(term))[-1]



def is_object_property(g: Graph, p: object) -> bool:
    return isinstance(p, URIRef) and (p, RDF.type, OWL.ObjectProperty) in g



def logical_axioms(g: Graph) -> Iterator[tuple[object, URIRef, object]]:
    """Every (subject, predicate, object) triple of `g` that states a logical axiom."""
    for predicate in AXIOM_PREDICATES:
        for subject, obj in g.subject_objects(predicate):
            # `[owl:inverseOf r]` inside a restriction is a property expression, not an axiom;
            # the restriction that contains it is what gets counted.
            if predicate == OWL.inverseOf and isinstance(subject, BNode):
                continue
            yield subject, predicate, obj
    for axiom_type in TYPED_AXIOMS:
        for subject in g.subjects(RDF.type, axiom_type):
            yield subject, RDF.type, axiom_type



def facts_for_axiom(g: Graph, s: object, p: URIRef, o: object) -> list[Fact] | None:
    """The facts one axiom contributes, or None when its shape is not supported."""
    if p == RDF.type:
        if o == OWL.FunctionalProperty and is_object_property(g, s):
            return [("Func", str(s))]
        return None
    if isinstance(s, BNode):
        # `[restriction] rdfs:subClassOf G`: a general inclusion with the restriction on the left.
        if p == RDFS.subClassOf and isinstance(o, URIRef):
            restriction = parse_restriction(g, s)
            return left_hand_facts(restriction, str(o)) if restriction else None
        return None
    subject = str(s)
    if p == RDFS.subClassOf and isinstance(o, BNode):
        restriction = parse_restriction(g, o)
        return right_hand_facts(subject, restriction) if restriction else None
    if p == OWL.equivalentClass:
        if isinstance(o, URIRef):
            return [("sub", subject, str(o)), ("sub", str(o), subject)]
        # `A ≡ R` is `A ⊑ R` and `R ⊑ A`; it is kept only when both halves are expressible.
        restriction = parse_restriction(g, o) if isinstance(o, BNode) else None
        lhs = left_hand_facts(restriction, subject) if restriction else None
        return right_hand_facts(subject, restriction) + lhs if restriction and lhs else None
    if p == OWL.equivalentProperty and isinstance(o, URIRef) and is_object_property(g, s):
        return [("subp", subject, str(o)), ("subp", str(o), subject)]
    if p == RDFS.range and isinstance(o, URIRef) and is_object_property(g, s):
        return [("Range", subject, str(o))]
    if p == RDFS.domain and isinstance(o, URIRef) and is_object_property(g, s):
        return [("Domain", subject, str(o))]
    if p in NAMED_AXIOMS and isinstance(o, URIRef):
        return [(NAMED_AXIOMS[p], subject, str(o))]
    return None



def blank_node_kind(g: Graph, node: BNode) -> str:
    """Which OWL construct a blank node is ('someValuesFrom', 'intersectionOf', ...), for the drop report."""
    return next((local(key) for key in RESTRICTION_KEYS if (node, key, None) in g), "blank")



def shape_label(g: Graph, s: object, p: URIRef, o: object) -> str:
    """A short name for an unsupported axiom's shape, so the drop report says what was lost."""
    if p == RDF.type:
        return local(o)
    if isinstance(s, BNode):
        if p == RDFS.subClassOf and isinstance(o, URIRef):
            return f"subClassOf/{blank_node_kind(g, s)}-subject"
        return f"{local(p)}/blank-subject"
    if isinstance(o, BNode):
        return f"{local(p)}/{blank_node_kind(g, o)}"
    return local(p)



def facts_of(g: Graph) -> tuple[list[Fact], Counter]:
    """All facts of one ontology, plus a count of the dropped axioms by shape."""
    facts: list[Fact] = []
    dropped: Counter = Counter()
    for s, p, o in sorted(logical_axioms(g), key=str):
        new_facts = facts_for_axiom(g, s, p, o)
        if new_facts is None:
            dropped[shape_label(g, s, p, o)] += 1
        else:
            facts.extend(new_facts)
    return facts, dropped



# inventories and output

def declared_classes(g: Graph) -> set[str]:
    return {str(c) for c in g.subjects(RDF.type, OWL.Class) if isinstance(c, URIRef)}



def declared_properties(g: Graph) -> set[str]:
    return {str(r) for r in g.subjects(RDF.type, OWL.ObjectProperty) if isinstance(r, URIRef)}



def inventory_facts(facts: list[Fact], classes: set[str], properties: set[str] = frozenset()) -> list[Fact]:
    """
    cls(C) and sub(C, T) for every class, prop(r) for every object property, whether declared
    or merely mentioned in a fact. The rule file derives sub(C, T) from cls(C) itself; the
    explicit rows keep the fact files readable on their own.
    """
    classes, properties = set(classes), set(properties)
    for fact in facts:
        relation, arguments = fact[0], fact[1:]
        for role, value in zip(SIGNATURES[relation], arguments):
            if role == "C":
                classes.add(value)
            elif role == "P":
                properties.add(value)
    classes.discard(THING)
    return ([("cls", c) for c in sorted(classes)]
            + [("sub", c, THING) for c in sorted(classes)]
            + [("prop", r) for r in sorted(properties)])



def mapping_facts(m: Mapping) -> list[Fact]:
    """An equivalence correspondence is two directed inclusions."""
    relation = "sub" if m.kind == "class" else "subp"
    return [(relation, m.e1, m.e2), (relation, m.e2, m.e1)]



def write_facts(facts_dir: Path, facts: list[Fact]) -> None:
    """
    One `<relation>.facts` file per relation, empty ones included; tab-separated, no trailing space.
    """
    facts_dir.mkdir(parents=True, exist_ok=True)
    for relation in RELATIONS:
        rows = ["\t".join(fact[1:]) + "\n" for fact in facts if fact[0] == relation]
        (facts_dir / f"{relation}.facts").write_text("".join(rows))



def write_with_mappings(facts: list[Fact], mappings: list[Mapping], facts_dir: Path) -> dict[str, list[Fact]]:
    """
    Append the mapping facts last, write every fact file, and return the mapping facts by mapping id.
    """
    by_mapping = {m.id: mapping_facts(m) for m in mappings}
    all_mapping_facts = [fact for facts_of_one in by_mapping.values() for fact in facts_of_one]
    write_facts(facts_dir, facts + all_mapping_facts)
    return by_mapping



def format_drops(drops: dict[str, Counter]) -> str:
    """
    The drop report, one line per ontology.
    """
    lines = ["Dropped axioms (unsupported shapes, per ontology):"]
    for name, counter in drops.items():
        body = ", ".join(f"{shape}: {n}" for shape, n in sorted(counter.items())) or "none"
        lines.append(f"  {name}: {body}")
    return "\n".join(lines)



def extract(g1: Graph, g2: Graph, mappings: list[Mapping], facts_dir: Path) -> tuple[dict[str, Counter], dict[str, list[Fact]]]:
    """
    Write the facts of both ontologies and of the mappings; return (drop report, mapping facts by id).
    """
    facts: list[Fact] = []
    drops: dict[str, Counter] = {}
    for name, g in (("o1", g1), ("o2", g2)):
        ontology_facts, drops[name] = facts_of(g)
        facts += ontology_facts + inventory_facts(ontology_facts, declared_classes(g), declared_properties(g))
    return drops, write_with_mappings(facts, mappings, facts_dir)
