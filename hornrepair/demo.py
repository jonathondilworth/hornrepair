"""
The `demo` subcommand: narrate one bundled witness, or print one summary row per witness.

    python -m hornrepair demo w1 [--normaliser hermit]
    python -m hornrepair demo --all [--normaliser hermit]

A narration prints, in this order: the axioms of both ontologies in Manchester syntax (read from
the Turtle, not from the facts), the alignment, the dropped-axiom report, the base facts, the
part of the closure that touches an unsatisfiable class or a mapped entity (base facts marked
[base], derived ones [derived]), the unsatisfiable classes, the blame sets, the mappings in no
blame set, and the README's one-sentence explanation of the witness. The summary table ends
every row with PASS or FAIL against the witness's expected.json. Outputs go to `out/demo/<witness>/`.
"""

import json
import re
from pathlib import Path

from rdflib import Graph
from rdflib.namespace import OWL

from hornrepair import manchester
from hornrepair.cli import run_pipeline
from hornrepair.extract import RELATIONS, Fact, format_drops
from hornrepair.matcher import Mapping

ROOT = Path(__file__).resolve().parent.parent
WITNESSES = ROOT / "tests" / "witnesses"
NAMES = ["w1", "w2", "w3", "w4", "w5", "w6",
         "d1_role", "d1_filler", "d1_subject", "d2_base", "d2_role", "d3_base", "d3_role",
         "d4_base", "d4_role", "d5_base", "d5_role", "d5_filler",
         "s1_definition", "s1_domain", "s2_definition", "s3_definition"]
PREFIXES = {"http://example.org/o1#": "o1:", "http://example.org/o2#": "o2:", str(OWL): "owl:"}


def short(iri: str) -> str:
    """`o1:Author` for the witness namespaces, the full IRI otherwise."""
    for namespace, prefix in PREFIXES.items():
        if iri.startswith(namespace):
            return prefix + iri[len(namespace):]
    return iri


def describe(m: Mapping) -> str:
    return f"{short(m.e1)} = {short(m.e2)}  [{m.kind}]"


def show_fact(fact: Fact) -> str:
    return f"{fact[0]}({', '.join(short(argument) for argument in fact[1:])})"


def read_facts(directory: Path, suffix: str) -> list[Fact]:
    """Every fact under `directory` (`facts/*.facts` or `closure/*.csv`), in RELATIONS order."""
    facts: list[Fact] = []
    for relation in RELATIONS:
        rows = (directory / f"{relation}{suffix}").read_text().splitlines()
        facts += [(relation, *row.split("\t")) for row in rows if row]
    return facts


def readme_lines(w: str) -> dict[str, str]:
    """
    The `Rules:` and `Why:` lines of the witness's section in README.md. The README is the one
    place those sentences are written, so the demo reads them rather than repeating them.
    """
    text = (ROOT / "README.md").read_text()
    section_match = re.search(rf"^### {w}\b.*?(?=^### |^## |\Z)", text, re.S | re.M)
    section_text = section_match[0] if section_match else ""
    return dict(re.findall(r"^(Rules|Why): (.+)$", section_text, re.M))


def run_witness(w: str, out: Path, normaliser: str) -> dict:
    """
    The pipeline result for a witness plus a PASS/FAIL verdict against its expected.json.
    On the identity path, w6 is expected to be refused; that refusal counts as a PASS.
    """
    expected = json.loads((WITNESSES / w / "expected.json").read_text())
    try:
        result = run_pipeline(WITNESSES / w / "o1.ttl", WITNESSES / w / "o2.ttl", out, normaliser)
    except ValueError as refusal:
        expected_refusal = expected.get("identity") == "raises" and normaliser == "identity"
        return {"error": str(refusal), "verdict": "PASS" if expected_refusal else "FAIL"}
    as_expected = (len(result["mappings"]) == expected["mappings"]
                   and result["unsat"] == set(expected["unsat"])
                   and {c: set(ms) for c, ms in result["blame"].items()}
                   == {c: set(ms) for c, ms in expected["blame"].items()})
    return {**result, "verdict": "PASS" if as_expected else "FAIL"}


def section(title: str, lines: list[str]) -> str:
    return title + "\n" + "\n".join(f"  {line}" for line in (lines or ["(none)"]))


def narrate(w: str, normaliser: str) -> str:
    out = ROOT / "out" / "demo" / w
    result = run_witness(w, out, normaliser)
    parts = [f"=== {w} ({normaliser} normaliser) ==="]
    for name in ("o1", "o2"):
        path = WITNESSES / w / f"{name}.ttl"
        parts.append(section(f"{name} axioms ({path.relative_to(ROOT)}):", manchester.axioms(Graph().parse(path))))
    if "error" in result:
        parts.append(f"normaliser: {result['error']}")
    else:
        base_facts = read_facts(out / "facts", ".facts")
        # The full closure is long; show only the facts that mention a class that clashed or an
        # entity the alignment touched, which is where the propagated restrictions are visible.
        of_interest = set(result["unsat"]) | {entity for m in result["mappings"] for entity in (m.e1, m.e2)}
        closure = [fact for fact in read_facts(out / "closure", ".csv") if of_interest & set(fact[1:])]
        by_id = {m.id: m for m in result["mappings"]}
        blame_lines = [f"{short(c)}: " + ", ".join(describe(by_id[m]) for m in ms)
                       for c, ms in result["blame"].items()]
        parts.append(section("Alignment:", [describe(m) for m in result["mappings"]]))
        parts.append(format_drops(result["drops"]))
        parts.append(section("Base facts:", [show_fact(fact) for fact in base_facts]))
        parts.append(section("Closure restricted to unsat classes and mapped entities:",
                             [f"{show_fact(fact)}  [{'base' if fact in base_facts else 'derived'}]"
                              for fact in closure]))
        parts.append(section("Unsatisfiable classes:", [short(c) for c in sorted(result["unsat"])]))
        parts.append(section("Blame sets (delete-one):", blame_lines))
        parts.append(section("Mappings in no blame set:", [describe(by_id[m]) for m in result["unblamed"]]))
    parts.append(f"Why: {readme_lines(w).get('Why', '(no README entry)')}")
    parts.append(f"Result: {result['verdict']} against expected.json")
    return "\n\n".join(parts) + "\n"


def table(normaliser: str) -> str:
    """One row per witness: name, mapping count, unsat count, blamed-mapping count, rules, verdict."""
    rows = [("witness", "mappings", "unsat", "blame", "rules exercised", "result")]
    for w in NAMES:
        result = run_witness(w, ROOT / "out" / "demo" / w, normaliser)
        rules = readme_lines(w).get("Rules", "")
        if "error" in result:
            rows.append((w, "-", "raises", "-", rules, result["verdict"]))
        else:
            blamed = set().union(*result["blame"].values()) if result["blame"] else set()
            rows.append((w, str(len(result["mappings"])), str(len(result["unsat"])), str(len(blamed)),
                         rules, result["verdict"]))
    widths = [max(len(row[column]) for row in rows) for column in range(6)]
    return "\n".join("  ".join(cell.ljust(widths[column]) for column, cell in enumerate(row)).rstrip()
                     for row in rows) + "\n"
