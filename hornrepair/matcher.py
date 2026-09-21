"""
Stage 1 of the pipeline: a lexical matcher.

Two entities of the same kind (class or object property) are mapped as equivalent when their
keys are identical, the key being the `rdfs:label` if there is one, else the IRI's local name,
lower-cased with everything but letters and digits removed. There is no fuzzy matching: the
matcher exists to produce an alignment to repair, not to be a good matcher.

The alignment is written as `alignment.tsv` (entity1, entity2, relation, confidence, kind).
Each mapping has a stable id, `<kind>:<entity1>|<entity2>`, which is what blame.json reports.
"""

import re
from pathlib import Path
from typing import NamedTuple

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS

KINDS = {"class": OWL.Class, "property": OWL.ObjectProperty} # TODO: include OWL.DataProperty

##
# A VERY SIMPLE MATCHER! (by design)
# - load ttl files
# - for every class and object (see todo above) property:
#       - the label becomes the key (if there is one) otherwise use the local name
# - if the same key occurs in both ontologies, match it with a confidence of 1.
##

class Mapping(NamedTuple):
    e1: str
    e2: str
    relation: str      # always "=" from this matcher
    confidence: float  # always 1.0 from this matcher
    kind: str          # "class" or "property"

    @property
    def id(self) -> str:
        return f"{self.kind}:{self.e1}|{self.e2}"



def label_key(g: Graph, entity: URIRef) -> str:
    """What two entities are compared on: label or local name, lower-case, letters and digits only."""
    label = g.value(entity, RDFS.label)
    text = str(label) if label is not None else re.split(r"[#/]", str(entity))[-1]
    return re.sub(r"[^a-z0-9]", "", text.lower())



def named_entities(g: Graph, kind: str) -> list[URIRef]:
    """The declared classes or object properties of `g`, sorted so the alignment order is stable."""
    return sorted(e for e in g.subjects(RDF.type, KINDS[kind]) if isinstance(e, URIRef))



def match(g1: Graph, g2: Graph) -> list[Mapping]:
    """Every pair of same-kind entities with identical keys; classes first, then properties."""
    mappings: list[Mapping] = []
    for kind in KINDS:
        keyed2 = [(label_key(g2, e2), e2) for e2 in named_entities(g2, kind)]
        for e1 in named_entities(g1, kind):
            key1 = label_key(g1, e1)
            for key2, e2 in keyed2:
                if key1 == key2:
                    mappings.append(Mapping(str(e1), str(e2), "=", 1.0, kind))
    return mappings



def write_alignment(mappings: list[Mapping], path: Path) -> None:
    rows = ["entity1\tentity2\trelation\tconfidence\tkind"]
    rows += [f"{m.e1}\t{m.e2}\t{m.relation}\t{m.confidence}\t{m.kind}" for m in mappings]
    path.write_text("\n".join(rows) + "\n")
