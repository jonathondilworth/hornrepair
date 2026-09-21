"""
HermiT cross-check of every fixture: the pipeline's unsatisfiable classes and delete-one blame sets must
agree with the reasoner on the merged ontology (see hornrepair/verify.py). Skipped without a JDK-style
java (jdk.compiler module) and the normaliser jar.
"""

from pathlib import Path

import pytest

from hornrepair import verify
from hornrepair.cli import run_pipeline
from tests.test_pipeline import REPORT_FIXTURES, WITNESSES

pytestmark = pytest.mark.skipif(not verify.available(), reason="java with jdk.compiler and normaliser.jar needed")


@pytest.mark.parametrize("w", ["w1", "w2", "w3", "w4", "w5", *REPORT_FIXTURES])
def test_agrees_with_hermit(w: str, tmp_path: Path) -> None:
    got = run_pipeline(WITNESSES / w / "o1.ttl", WITNESSES / w / "o2.ttl", tmp_path, "identity")
    assert verify.check(WITNESSES / w / "o1.ttl", WITNESSES / w / "o2.ttl", tmp_path, got) == []


def test_w6_agrees_with_hermit(tmp_path: Path) -> None:
    got = run_pipeline(WITNESSES / "w6" / "o1.ttl", WITNESSES / "w6" / "o2.ttl", tmp_path, "hermit")
    assert verify.check(WITNESSES / "w6" / "o1.ttl", WITNESSES / "w6" / "o2.ttl", tmp_path, got) == []
