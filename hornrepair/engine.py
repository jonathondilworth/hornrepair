"""
Compute the closure of a facts directory with Soufflé and read back the unsatisfiable classes.

The whole engine is one command:

    souffle -F <facts_dir> -D <out_dir> rules/repair.dl

Every `.input` relation of the rule file is read from `<facts_dir>/<name>.facts` (tab-separated,
one tuple per line), every `.output` relation is written to `<out_dir>/<name>.csv` in the same
format, and `unsat.csv` is the answer. The command line is echoed to stderr so any run can be
repeated by hand.
"""

import shutil
import subprocess
import sys
from pathlib import Path

RULES = Path(__file__).resolve().parent.parent / "rules" / "repair.dl"

INSTALL_HINT = "install Soufflé (https://souffle-lang.github.io, 2.4 tested) and put `souffle` on PATH"


def require_souffle() -> None:
    """Fail early, with a clear message, when the `souffle` binary is not available."""
    if shutil.which("souffle") is None:
        raise FileNotFoundError(f"`souffle` not found on PATH; {INSTALL_HINT}")


def run(facts_dir: Path, out_dir: Path, rules: Path = RULES) -> set[str]:
    """Close `facts_dir` under `rules` into `out_dir`; return the IRIs listed in `out_dir/unsat.csv`."""
    require_souffle()
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["souffle", "-F", str(facts_dir), "-D", str(out_dir), str(rules)]
    print("+ " + " ".join(cmd), file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"souffle failed (exit {proc.returncode}):\n{proc.stderr}")
    lines = (out_dir / "unsat.csv").read_text().splitlines()
    return {line.strip() for line in lines if line.strip()}
