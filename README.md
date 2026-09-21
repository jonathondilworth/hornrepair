# hornrepair

This hornrepair repository provides a _proof-of-concept_ that detects unsatisfiabilities introduced by cardinality restrictions during ontology matching pipelines. The demonstration uses [souffle-flavoured datalog rules](rules/repair.dl) with a [(naive) matching pipeline implemented in Python](hornrepair/cli.py). 

Specifically, it finds classes that an alignment makes unsatisfiable through existential, universal and cardinality restrictions. This is a class of conflict that a _class hierarchy plus disjointness projection_ cannot see. It does so with a sound-but-incomplete Horn approximation of the merged ontologies, executed as a Souffle datalog program, and reports for each unsatisfiable class the mappings whose removal would restore coherence.

## Install

    uv venv .venv && uv pip install rdflib pytest
    # check that Souffle is on PATH (see below)
    souffle --version
    # HermiT normaliser and reasoner
    cd normaliser && mvn -q package && cd ..

### Souffle

The closure is computed by Souffle. Check the installation with `souffle --version`. Alternatively, set it up for:

**Debian and Ubuntu**

- Download the `.deb` for your release from https://github.com/souffle-lang/souffle/releases
- We use Version 2.4.1.
- run `sudo apt install ./<package>.deb`.

**macOS**

- Run `brew install souffle`.

**Other Operating Systems**

- You can always build from the source as described at https://souffle-lang.github.io/build

## Rules

The [datalog rules](rules/repair.dl) include subsumption rules S1–S3 (saturation of `some`/`only`/`atleast`/`atmost` along the class and property hierarchies), clash rules D1–D5, and left-hand restriction relations (`someLHS`, `onlyLHS`, `atleastLHS`, `atmostLHS`) through which a restriction reaches a named class.

## Demo & Usage

    python -m hornrepair demo w1                      # narrate one bundled witness
    python -m hornrepair demo --all                   # narrate every witness, one row each with PASS/FAIL against expected output
    python -m hornrepair demo w6 --normaliser hermit  # run the nested-filler witness through HermiT
    
    # for arbitrary input-output run:
    python -m hornrepair run --o1 A.ttl --o2 B.ttl --out DIR [--normaliser hermit]

    # to run the included tests:
    pytest -q

The `demo` prints axioms of both input ontologies, the alignment, reports dropped axioms, the base facts, the closure on the classes, the unsatisfiable classes, the blame sets, and the explanation for that witness. Whereas, `run` writes `alignment.tsv`, `facts/`, `closure/`, `blame/`, `blame.json` and `report.txt` into the output directory `DIR`.

## Examples (Witnesses, Restriction-essential cases)

The full list of general witnesses and the restriction-essential cases are provided in [examples.md](./examples.md). These include W1-W6 as general examples with D1-D5 (and their variations) as examples for which the clash rules fire. You can also review the actual ontologies that correspond to the examples under the [tests/witnesses](tests/witnesses/) directory.

## Experiments: Ontology Alignment Repair

A _repair_ transforms $\mathcal{M}$ into $\mathcal{M}^{\prime}$ through two potential operations applied to any correspondence $m \in \mathcal{M}$: (i) discarding, and (ii) weakening an equivalence to one of its two directions. These operations should apply to **both class and to property correspondences**. That is, a property equivalence $r \equiv s$ may be weakened to $r \sqsubseteq s$ or to $s \sqsubseteq r$ similarly to a class equivalence may. We define a repair as **effective** if $U(\mathcal{O}_{\mathcal{M}^{\prime}}) = \varnothing$, noting that its cost (per our methodology) is modelled by the loss

$$
loss(\mathcal{M}, \mathcal{M}^{\prime}) = \sum \lbrace\, c_m \mid m \in \mathcal{M} \text{ discarded} \,\rbrace + \tfrac{1}{2} \sum \lbrace\, c_m \mid m \in \mathcal{M} \text{ weakened} \,\rbrace,
$$

such that weakening retains half of a correspondence's value. Among all effective repairs we prefer those that minimise this loss.

### Testing Existing Matchers on the Witnesses

The witnesses also serve to probe what current matchers do with **restriction-essential (RE)** cases/conflicts. Every pair was given to _stock_ LogMap (in its default configuration), to our [LogMap fork](#) that carries the restriction-aware repair, and to AgreementMakerLight (AML), where every output alignment was coherence-scored with HermiT. 

We then check to see if the restriction-essential case was resolved (by any valid repair). An alignment is considered "over-repaired" when it is coherent and its loss exceeds the minimal effective loss for that witness (over all 22 witnesses). Of course, for a matcher that simply does not perform property matching, unsatisfiabilities will not be introduced (e.g., AML in automatic mode). Indeed, by conservatively rejecting property correspondences, the systems can effectively avoid conflicts, but may also discard potentially useful and important connections. It is also important to note that AML does not perform weakening.

| Configuration | = example matcher | coherent | resolves RE | minimal-loss RE | over-repaired |
|---|---|---|---|---|---|
| stock LogMap | 17/22 | 7/22 | 4/19 | 0/19 | 5/22 |
| Our LogMap fork, restriction repair on | 2/22 | 22/22 | 19/19 | 11/19 | 9/22 |
| AML, automatic mode as shipped | 0/22 | 22/22 | 19/19 | 0/19 | 22/22 |
| AML, automatic mode, property matching on | 16/22 | 7/22 | 4/19 | 0/19 | 5/22 |
| AML, manual mode, property matching on | 21/22 | 3/22 | 0/19 | 0/19 | 1/22 |

The example matcher is hornrepair's own lexical alignment, with all equivalences at confidence 1. We assume it is what one would expect a matcher to propose on these pairs. 

*= example matcher* counts outputs identical to it. *coherent* counts outputs whose merged theory is HermiT-coherent (weakened correspondences are considered as one-directional inclusions, **not equivalences**). The remaining columns treat each output as a repair of the example alignment under the above-mentioned loss. 

*resolves RE* means "the matcher resolved the restriction-essential case". That is, it is coherent and every change is confined to a blamed correspondence. Note that if a property correspondence is never proposed, it can technically be counted as "discarded", so an output can resolve a case simply by omission. 

*minimal-loss RE* means resolved at the minimum loss, which is found by enumerating repairs over the blamed correspondences and testing each with HermiT. **For every incoherence-inducing witness that minimum is one weakening**. *over-repaired* counts coherent outputs whose loss exceeds the minimum.

## Roadmap / Future Work

* Modify the LogMap fork to include weakening property correspondences (at present it achieves minimal-loss on some examples by class weakening).
* **TODO: extend this list.**