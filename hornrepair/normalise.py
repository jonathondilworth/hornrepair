"""
Stage 2 of the pipeline: normalisation, so that every restriction has a named filler.

Two normalisers:

  * `normalise`, the identity: returns the graph unchanged after checking that every
    `owl:someValuesFrom` and `owl:allValuesFrom` filler is a named class, and raises with the
    offending axiom otherwise. A nested filler such as `writes some (Book and publishedBy some
    Publisher)` cannot be written as a fact and needs HermiT.
  * `hermit`: writes the graph as RDF/XML, runs HermiT's structural normalisation through
    `normaliser/target/normaliser.jar`, and returns the path of the clause file it produced.
    HermiT names every nested filler with a fresh class `internal:def#k` and records what the
    fresh class is defined by; extract_clauses.py then reads those clauses instead of the Turtle.
"""

import subprocess
import sys
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDFS

from hornrepair.manchester import expr

JAR = Path(__file__).resolve().parent.parent / "normaliser" / "target" / "normaliser.jar"
BUILD = "cd normaliser && mvn -q package"


def normalise(g: Graph) -> Graph:
    """Return `g` unchanged; raise if any some/allValuesFrom filler is not a named class."""
    for predicate in (OWL.someValuesFrom, OWL.allValuesFrom):
        for restriction, filler in g.subject_objects(predicate):
            if not isinstance(filler, URIRef):
                owner = g.value(predicate=RDFS.subClassOf, object=restriction)
                raise ValueError(
                    f"complex filler in `{expr(g, owner)} SubClassOf {expr(g, restriction)}`: "
                    f"the identity normaliser accepts only named fillers; use --normaliser hermit"
                )
    return g


def hermit(g: Graph, work_dir: Path, name: str) -> Path:
    """
    Write `g` as RDF/XML to `work_dir/<name>.owl`, run the HermiT normaliser jar on it, and
    return the path of the resulting `work_dir/<name>.clauses`. Both files are kept for inspection.
    """
    if not JAR.exists():
        raise FileNotFoundError(f"normaliser jar not found at {JAR}; build it with: {BUILD}")
    work_dir.mkdir(parents=True, exist_ok=True)
    owl, clauses = work_dir / f"{name}.owl", work_dir / f"{name}.clauses"
    g.serialize(destination=str(owl), format="xml")
    cmd = ["java", "-jar", str(JAR), str(owl), str(clauses)]
    print("+ " + " ".join(cmd), file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"normaliser failed (exit {proc.returncode}):\n{proc.stderr}")
    return clauses
