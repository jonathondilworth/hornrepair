"""
The command line:

    python -m hornrepair run --o1 O1.ttl --o2 O2.ttl --out OUT_DIR [--normaliser identity|hermit]
    python -m hornrepair demo WITNESS | --all [--normaliser identity|hermit]

`run_pipeline` is the one function every stage passes through, in this order:

    1. matcher.match        lexical alignment of the two ontologies        -> OUT/alignment.tsv
    2. normalise            every restriction filler must be a named class -> OUT/hermit/*.owl, *.clauses (hermit only)
    3. extract              axioms and mappings -> Horn facts              -> OUT/facts/<relation>.facts
    4. engine.run           Soufflé closure                                -> OUT/closure/<relation>.csv, unsat.csv
    5. blame.blame          delete-one reruns, one per mapping             -> OUT/blame/<i>/, OUT/blame.json
    6. write_report         a human-readable summary                       -> OUT/report.txt

The tests call `run_pipeline` directly, so they exercise exactly what the command line runs.
"""

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

from rdflib import Graph

from hornrepair import blame, engine, extract, extract_clauses, matcher, normalise
from hornrepair.matcher import Mapping

LIMITATION = ("Limitation: delete-one lists only the mappings present in EVERY derivation of an unsat\n"
              "class (the intersection of its justifications). A class with two independent causes\n"
              "gets a partial or empty blame set. No repair is chosen and nothing is fed back.")



def run_pipeline(o1: Path, o2: Path, out: Path, normaliser: str = "identity") -> dict:
    """
    Run every stage into `out`, write report.txt, and return what the tests compare.
    """
    g1 = Graph().parse(o1, format="turtle")
    g2 = Graph().parse(o2, format="turtle")

    out.mkdir(parents=True, exist_ok=True)

    mappings = matcher.match(g1, g2)  # always on the original Turtle, never on normalised clauses
    matcher.write_alignment(mappings, out / "alignment.tsv")

    if normaliser == "hermit":
        clauses1 = normalise.hermit(g1, out / "hermit", "o1")
        clauses2 = normalise.hermit(g2, out / "hermit", "o2")
        drops, mapping_facts = extract_clauses.extract(clauses1, clauses2, mappings, out / "facts")
    else:
        drops, mapping_facts = extract.extract(normalise.normalise(g1), normalise.normalise(g2), mappings, out / "facts")

    unsat = engine.run(out / "facts", out / "closure")
    blamed, unblamed = blame.blame(unsat, mapping_facts, out / "facts", out / "blame")
    (out / "blame.json").write_text(json.dumps(blamed, indent=2) + "\n")
    write_report(out / "report.txt", f"hornrepair report: {o1} vs {o2}", mappings, drops, unsat, blamed, unblamed)

    return {"mappings": mappings, "drops": drops, "unsat": unsat, "blame": blamed, "unblamed": unblamed}



def write_report(path: Path, title: str, mappings: list[Mapping], drops: dict[str, Counter], unsat: set[str], blamed: dict[str, list[str]], unblamed: list[str]) -> None:
    """
    report.txt: the drop counts, the alignment, the unsatisfiable classes, and the blame sets.
    """
    describe = {m.id: f"{m.e1} = {m.e2}  [{m.kind}]" for m in mappings}
    blame_lines = [c + "".join(f"\n    - {describe[m]}" for m in ms) for c, ms in blamed.items()]
    lines = [title, "", extract.format_drops(drops), ""]
    lines += section(f"Mappings ({len(mappings)}):", list(describe.values()))
    lines += section(f"Unsatisfiable classes ({len(unsat)}):", sorted(unsat))
    lines += section("Blame sets (mappings whose removal clears the unsatisfiability):", blame_lines)
    lines += section(f"Mappings in no blame set ({len(unblamed)}):", [describe[m] for m in unblamed])
    lines.append(LIMITATION)
    path.write_text("\n".join(lines) + "\n")



def section(title: str, items: list[str]) -> list[str]:
    """
    A titled block of indented items, '(none)' when empty, followed by a blank line.
    """
    return [title, *(f"  {item}" for item in (items or ["(none)"])), ""]


def main(argv: list[str] | None = None) -> int:
    from hornrepair import demo  # imported here because demo itself imports run_pipeline

    parser = argparse.ArgumentParser(prog="hornrepair", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="match, normalise, extract, close, and blame two Turtle files")

    for flag in ("--o1", "--o2", "--out"):
        run.add_argument(flag, required=True, type=Path)

    show = commands.add_parser("demo", help="narrate a bundled witness, or --all for the summary table")
    show.add_argument("witness", nargs="?", choices=demo.NAMES)
    show.add_argument("--all", action="store_true")

    for command in (run, show):
        command.add_argument("--normaliser", choices=("identity", "hermit"), default="identity")

    args = parser.parse_args(argv)

    if shutil.which("souffle") is None:
        sys.exit(f"hornrepair: `souffle` not found on PATH; {engine.INSTALL_HINT}")
    try:
        if args.command == "demo":
            if not args.all and not args.witness:
                parser.error("demo needs a witness name or --all")
            print(demo.table(args.normaliser) if args.all else demo.narrate(args.witness, args.normaliser), end="")
        else:
            run_pipeline(args.o1, args.o2, args.out, args.normaliser)
            print((args.out / "report.txt").read_text(), end="")
    except (FileNotFoundError, ValueError) as e:
        sys.exit(f"hornrepair: {e}")
    return 0
