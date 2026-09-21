"""
Stage 5 of the pipeline: delete-one blame.

For each mapping, the closure is recomputed with that mapping's two facts removed. A mapping
is blamed for an unsatisfiable class when the class becomes satisfiable without it. This finds
the mappings present in every derivation of `unsat(c)`; a class with two independent causes
survives the removal of either one and gets a partial or empty blame set.

Every rerun is kept under `work_dir/<i>/` (facts, closure, and a `removed.txt` naming the
mapping) so that it can be inspected or repeated by hand.
"""

from pathlib import Path

from hornrepair.engine import run
from hornrepair.extract import Fact


def write_facts_without(source: Path, target: Path, removed: list[Fact]) -> None:
    """
    Copy every .facts file from `source` to `target`, leaving out the rows in `removed`.
    """
    target.mkdir(parents=True, exist_ok=True)
    removed_rows = {(fact[0], "\t".join(fact[1:])) for fact in removed}
    for path in sorted(source.glob("*.facts")):
        relation = path.stem
        rows = path.read_text().splitlines()
        kept = [row for row in rows if (relation, row) not in removed_rows]
        (target / path.name).write_text("".join(row + "\n" for row in kept))


def blame(unsat: set[str], mapping_facts: dict[str, list[Fact]], facts_dir: Path, work_dir: Path) -> tuple[dict[str, list[str]], list[str]]:
    """
    Return ({unsat class: [ids of the mappings whose removal clears it]}, [ids blamed for nothing]).
    Mapping i, in alignment order, is rerun under `work_dir/<i>/`.
    """
    if not unsat:
        return {}, list(mapping_facts)
    still_unsat: dict[str, set[str]] = {}
    for i, (mapping_id, facts) in enumerate(mapping_facts.items()):
        rerun = work_dir / str(i)
        write_facts_without(facts_dir, rerun / "facts", facts)
        (rerun / "removed.txt").write_text(mapping_id + "\n")
        still_unsat[mapping_id] = run(rerun / "facts", rerun / "closure")
    blamed = {c: [m for m in mapping_facts if c not in still_unsat[m]] for c in sorted(unsat)}
    unblamed = [m for m in mapping_facts if not any(m in blamed_for_c for blamed_for_c in blamed.values())]
    return blamed, unblamed
