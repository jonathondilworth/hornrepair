"""
End-to-end tests over the bundled witnesses.

Every witness in tests/witnesses/<name>/ is run through `run_pipeline`, exactly as the command
line runs it, and compared with its expected.json: the number of mappings, the unsatisfiable
classes, and each blame set (as a set). Two extra tests lock in the direction of the two
anti-monotone property rules: with the rule flipped, the satisfiable controls w2 and w4 must
turn into a specific spurious unsat, which proves the suite would catch the wrong polarity.
The flipped rule file is written to the test's temporary directory; rules/repair.dl is never modified.
"""

import json
from pathlib import Path

import pytest

from hornrepair.cli import run_pipeline
from hornrepair.engine import RULES, run
from hornrepair.normalise import JAR

WITNESSES = Path(__file__).parent / "witnesses"
O1, O2 = "http://example.org/o1#", "http://example.org/o2#"

# witness -> (the rule as written, the same rule made monotone in the property, the spurious unsat that causes)
FLIPS = {
    "w2": ("only(a, r, f) :- only(a, s, f), subp(r, s).", "only(a, s, f) :- only(a, r, f), subp(r, s).",
           {O1 + "Editor", O2 + "Editor"}),
    "w4": ("atmost(a, s, n, f) :- atmost(a, r, n, f), subp(s, r).", "atmost(a, s, n, f) :- atmost(a, r, n, f), subp(r, s).",
           {O1 + "Paper", O2 + "Paper"}),
}


def expected(w: str) -> dict:
    return json.loads((WITNESSES / w / "expected.json").read_text())


def pipeline(w: str, out: Path, normaliser: str = "identity") -> dict:
    return run_pipeline(WITNESSES / w / "o1.ttl", WITNESSES / w / "o2.ttl", out, normaliser)


def check(got: dict, want: dict, out: Path) -> None:
    assert len(got["mappings"]) == want["mappings"]
    assert got["unsat"] == set(want["unsat"])
    assert got["blame"].keys() == want["blame"].keys()
    for c, ms in want["blame"].items():
        assert set(got["blame"][c]) == set(ms), c
    assert json.loads((out / "blame.json").read_text()) == got["blame"]
    assert "Dropped axioms" in (out / "report.txt").read_text()


REPORT_FIXTURES = [
    "d1_role", "d1_filler", "d1_subject",
    "d2_base", "d2_role",
    "d3_base", "d3_role",
    "d4_base", "d4_role",
    "d5_base", "d5_role", "d5_filler",
    "s1_definition", "s1_domain", "s2_definition", "s3_definition",
]


@pytest.mark.parametrize("w", ["w1", "w2", "w3", "w4", "w5", *REPORT_FIXTURES])
def test_witness(w: str, tmp_path: Path) -> None:
    check(pipeline(w, tmp_path), expected(w), tmp_path)


def test_w6_identity_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="writes some \\(Book and publishedBy some Publisher\\)"):
        pipeline("w6", tmp_path)


@pytest.mark.xfail(not JAR.exists(), reason="normaliser jar not built; see NOTES.md (SPEC-SEMINAR 11)")
def test_w6_hermit(tmp_path: Path) -> None:
    got = pipeline("w6", tmp_path, "hermit")
    check(got, expected("w6"), tmp_path)
    some = {tuple(line.split("\t")) for line in (tmp_path / "closure" / "some.csv").read_text().splitlines()}
    assert (O1 + "Author", O2 + "writes", O2 + "Book") in some
    assert any(a == O1 + "Author" and r == O2 + "writes" and f.startswith("internal:def#") for a, r, f in some)


@pytest.mark.parametrize("w", ["w2", "w4"])
def test_flipped_polarity_is_unsat(w: str, tmp_path: Path) -> None:
    """A property-monotone `only` (w2) or `max` (w4) rule must flag the satisfiable control."""
    correct, flipped, spurious = FLIPS[w]
    rules = RULES.read_text()
    assert rules.count(correct) == 1
    (tmp_path / "flipped.dl").write_text(rules.replace(correct, flipped))
    assert pipeline(w, tmp_path / w)["unsat"] == set()
    unsat = run(tmp_path / w / "facts", tmp_path / "flipped", tmp_path / "flipped.dl")
    assert unsat, f"{w}: flipped polarity must produce a spurious unsat"
    assert unsat == spurious
