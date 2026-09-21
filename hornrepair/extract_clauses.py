"""
Stage 3 of the pipeline, HermiT path: the clause files written by the normaliser jar -> the same
fact files that extract.py writes from Turtle.

A clause line is one of

    C <TAB> literal <TAB> literal ...     a disjunction of literals, each '+atom' or '-atom'
    P <TAB> sub-iri <TAB> super-iri       a simple object-property inclusion

where an atom is a class IRI, `some(r,F)`, `only(r,F)`, `min(n,r,F)`, `max(n,r,F)`, or
`other(...)` for anything HermiT produced that the grammar does not cover. A property `r` may
be `inv(iri)` and a filler `F` may be `~iri`; neither is supported here.

Only Horn shapes become facts; every other clause is dropped and counted by shape:

    -A +B              sub(A, B)              -A -B                disj(A, B)
    -A +some(r,F)      some(A, r, F)          -some(r,F) +G        someLHS(r, F, G)       (likewise only, min, max)
    +only(r,F)         only(T, r, F)          +max(n,r,F)          atmost(T, r, n, F)     (unit clauses: a range or a
    P r s              subp(r, s)                                                          functionality axiom)
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import NamedTuple

from hornrepair.extract import LHS_OF, THING, Fact, inventory_facts, write_with_mappings
from hornrepair.matcher import Mapping


class Literal(NamedTuple):
    sign: str          # '+' or '-'
    kind: str          # named | some | only | min | max | other
    args: list[str]    # [iri] for named; [r, F] for some/only; [n, r, F] for min/max; [text] for other


# HermiT's literal kinds -> the rule file's relations (the clause grammar says min/max).
RELATION_OF = {"some": "some", "only": "only", "min": "atleast", "max": "atmost"}



def parse_literal(text: str) -> Literal:
    """'+some(r,F)' -> Literal('+', 'some', ['r', 'F']);  '-A' -> Literal('-', 'named', ['A'])."""
    sign, atom = text[0], text[1:]
    if atom.startswith("other("):
        return Literal(sign, "other", [atom])
    match = re.fullmatch(r"(some|only|min|max)\((.*)\)", atom)
    if match:
        return Literal(sign, match[1], match[2].split(","))
    return Literal(sign, "named", [atom])



def right_hand_fact(a: str, restriction: Literal) -> Fact:
    """The fact for `a ⊑ R`."""
    relation = RELATION_OF[restriction.kind]
    if restriction.kind in ("some", "only"):
        r, f = restriction.args
        return (relation, a, r, f)
    n, r, f = restriction.args
    return (relation, a, r, n, f)



def left_hand_fact(restriction: Literal, g: str) -> Fact:
    """The fact for `R ⊑ g`."""
    relation = LHS_OF[RELATION_OF[restriction.kind]]
    if restriction.kind in ("some", "only"):
        r, f = restriction.args
        return (relation, r, f, g)
    n, r, f = restriction.args
    return (relation, r, n, f, g)



def is_unsupported(literal: Literal) -> bool:
    """`other(...)`, an inverse property, or a complement filler: nothing in the rule file can use it."""
    return literal.kind == "other" or any(arg.startswith(("inv(", "~")) for arg in literal.args)



def facts_for_clause(literals: list[Literal]) -> list[Fact] | None:
    """The facts a concept-inclusion clause contributes, or None when it is not a supported Horn shape."""
    if any(is_unsupported(literal) for literal in literals):
        return None
    if len(literals) == 1:
        (literal,) = literals
        # HermiT writes a range axiom as the unit clause `+only(r,G)` and a functionality axiom
        # as `+max(1,r,T)`; both hold of every individual, so they attach to T.
        if literal.sign == "+" and literal.kind in ("only", "max"):
            return [right_hand_fact(THING, literal)]
        return None
    if len(literals) != 2:
        return None
    first, second = literals
    if first.kind == "named" and second.kind == "named":
        signs = first.sign + second.sign
        if signs == "--":
            return [("disj", first.args[0], second.args[0])]
        if signs == "-+":
            return [("sub", first.args[0], second.args[0])]
        if signs == "+-":
            return [("sub", second.args[0], first.args[0])]
        return None  # two positive literals: a disjunction, which is where domain axioms land
    named = [literal for literal in literals if literal.kind == "named"]
    restrictions = [literal for literal in literals if literal.kind in RELATION_OF]
    if len(named) == 1 and len(restrictions) == 1:
        (a,), (restriction,) = named, restrictions
        if a.sign == "-" and restriction.sign == "+":
            return [right_hand_fact(a.args[0], restriction)]   # -A +R  is  A ⊑ R
        if a.sign == "+" and restriction.sign == "-":
            return [left_hand_fact(restriction, a.args[0])]    # -R +A  is  R ⊑ A
    return None



def clause_shape(literals: list[Literal]) -> str:
    """
    A short name for a dropped clause's shape, for the drop report.
    """
    if len(literals) > 2:
        return "3+ literals"
    if any(literal.kind == "other" for literal in literals):
        return "other(...)"
    if any(is_unsupported(literal) for literal in literals):
        return "inverse property or complement filler"
    positives = sum(literal.sign == "+" for literal in literals)
    return f"{len(literals)} literals, {positives} positive"



def facts_of(clauses: Path) -> tuple[list[Fact], Counter, set[str]]:
    """
    The facts of one clause file, the dropped clauses by shape, and every named class mentioned.
    """
    facts: list[Fact] = []
    dropped: Counter = Counter()
    classes: set[str] = set()
    for line in clauses.read_text().splitlines():
        kind, *fields = line.split("\t")
        if kind == "P":
            sub_property, super_property = fields
            facts.append(("subp", sub_property, super_property))
            continue
        literals = [parse_literal(field) for field in fields]
        classes.update(literal.args[0] for literal in literals if literal.kind == "named")
        new_facts = facts_for_clause(literals)
        if new_facts is None:
            dropped[clause_shape(literals)] += 1
        else:
            facts.extend(new_facts)
    return facts, dropped, classes



def extract(clauses1: Path, clauses2: Path, mappings: list[Mapping], facts_dir: Path) -> tuple[dict[str, Counter], dict[str, list[Fact]]]:
    """
    Same contract as extract.extract, reading HermiT clause files instead of Turtle.
    """
    facts: list[Fact] = []
    drops: dict[str, Counter] = {}
    for name, path in (("o1", clauses1), ("o2", clauses2)):
        ontology_facts, drops[name], classes = facts_of(path)
        facts += ontology_facts + inventory_facts(ontology_facts, classes)
    return drops, write_with_mappings(facts, mappings, facts_dir)
