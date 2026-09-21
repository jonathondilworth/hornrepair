"""
HermiT cross-check of a pipeline result, through verify/Coherence.java run on the normaliser jar
(HermiT 1.3.8 with OWL API 4.1.3).

For a witness pair and its alignment the checker answers two questions: which named classes of
O1 U O2 U ax(M) are unsatisfiable according to HermiT, and whether each input ontology is
coherent on its own (the precondition the report assumes). `check` then compares a pipeline
result with the reasoner on three counts: the unsat sets agree, removing each blamed mapping
clears the class it is blamed for, and removing each unblamed mapping does not. Those three
statements are delete-one blame restated as reasoner queries.

The checker is launched as a single-file source program, so a JDK (the `jdk.compiler` module)
is needed; `available()` says whether it is, and the tests skip when it is not.
"""

import shutil
import subprocess
from pathlib import Path

from hornrepair.normalise import JAR

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "verify" / "Coherence.java"


def available() -> bool:
    if shutil.which("java") is None or not JAR.exists() or not CHECKER.exists():
        return False
    modules = subprocess.run(["java", "--list-modules"], capture_output=True, text=True).stdout
    return "jdk.compiler" in modules


def unsat(o1: Path, o2: Path, alignment: Path, without: list[str] = ()) -> tuple[set[str], bool, bool]:
    """(HermiT's unsatisfiable classes of the merge without the mappings in `without`, o1 coherent?, o2 coherent?)"""
    cmd = ["java", "--add-opens", "java.base/java.lang=ALL-UNNAMED", "-cp", str(JAR), str(CHECKER),
           str(o1), str(o2), str(alignment), "--without", *without]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"HermiT checker failed (exit {proc.returncode}):\n{proc.stderr[-2000:]}")
    # The checker prints "o1-coherent: true|false", then "o2-coherent: ...", then one class per line.
    lines = [line for line in proc.stdout.splitlines()
             if line.strip() and not line.startswith(("SLF4J", "log4j"))]
    o1_coherent = lines[0] == "o1-coherent: true"
    o2_coherent = lines[1] == "o2-coherent: true"
    return set(lines[2:]), o1_coherent, o2_coherent


def check(o1: Path, o2: Path, out: Path, result: dict) -> list[str]:
    """The disagreements between `result` (from run_pipeline) and HermiT; an empty list means they agree."""
    alignment = out / "alignment.tsv"
    problems: list[str] = []
    hermit_unsat, o1_coherent, o2_coherent = unsat(o1, o2, alignment)
    if not o1_coherent or not o2_coherent:
        problems.append(f"input ontology incoherent on its own (o1={o1_coherent}, o2={o2_coherent})")
    if hermit_unsat != result["unsat"]:
        problems.append(f"unsat: hermit={sorted(hermit_unsat)} pipeline={sorted(result['unsat'])}")
    for mapping in result["mappings"]:
        still_unsat, _, _ = unsat(o1, o2, alignment, [mapping.id])
        for c in result["unsat"]:
            blamed = mapping.id in result["blame"].get(c, [])
            if blamed and c in still_unsat:
                problems.append(f"{c}: removing {mapping.id} is blamed but does not clear it (HermiT)")
            if not blamed and c not in still_unsat and c in hermit_unsat:
                problems.append(f"{c}: removing {mapping.id} clears it (HermiT) but is not blamed")
    return problems
