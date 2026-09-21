# Examples

General examples are covered under w1-w6. The clash rules for D1-D5 (alongisde their variations) are presented below the general examples.

## General Example Witnesses

### w1 — a conflict through some and only

o1: Author SubClassOf Person; Author SubClassOf writes some Book; Book SubClassOf Document.
o2: Author SubClassOf writes only Article; Book DisjointWith Article.
Mappings: Author, Book, Document, writes.
Rules: existential (filler, property); universal (inherited); clashes (some/only/disj)
Expected: unsat o1:Author and o2:Author; blame Author, Book, writes; Document blamed for nothing.
Why: Every author writes something that is a Book, the Book mapping makes that thing an o2 Book, the writes mapping makes it an o2 writes-successor, and o2 says every writes-successor of an Author is an Article, which is disjoint from Book, so there can be no Author at all.

### w2 — the satisfiable control for only

o1: Editor SubClassOf edits some Book.
o2: Editor SubClassOf reviews only Article; reviews SubPropertyOf edits; Book DisjointWith Article.
Mappings: Editor, Book, edits.
Rules: existential (property); universal (inherited); the anti-monotone property rule does not fire
Expected: nothing unsatisfiable.
Why: The universal restriction constrains only the things an Editor reviews, and the Book an Editor must edit need not be reviewed, so an editor with one edited Book and nothing reviewed satisfies everything.
Wrong polarity: A property-monotone only rule would lift the Article restriction from reviews up to edits and report both Editors unsatisfiable.

### w3 — a min/max clash

o1: Paper SubClassOf hasReviewer min 2 Reviewer.
o2: Paper SubClassOf hasReviewer max 1 Person; Reviewer SubClassOf Person.
Mappings: Paper, hasReviewer, Reviewer.
Rules: min (filler, property); max (inherited); clashes (min/max)
Expected: unsat o1:Paper and o2:Paper; blame all three mappings.
Why: Two reviewers are two persons once Reviewer is mapped and sits under Person, so a Paper needs at least two hasReviewer-successors in Person while o2 allows at most one, and no Paper can exist.

### w4 — the satisfiable control for max

o1: Paper SubClassOf hasReviewer min 2 Reviewer.
o2: Paper SubClassOf hasLeadReviewer max 1 Person; hasLeadReviewer SubPropertyOf hasReviewer; Reviewer SubClassOf Person.
Mappings: Paper, hasReviewer, Reviewer.
Rules: min (filler, property); max (inherited); the anti-monotone property rule does not fire
Expected: nothing unsatisfiable.
Why: The bound applies to lead reviewers only, and neither of the two reviewers a Paper needs has to be a lead reviewer, so a Paper with two plain reviewers is fine.
Wrong polarity: A property-monotone max rule would push the bound up from hasLeadReviewer to hasReviewer and report both Papers unsatisfiable.

### w5 — an unsatisfiable filler chain

o1: Student SubClassOf enrolledIn some Programme; Programme SubClassOf Course.
o2: Programme SubClassOf Degree; Degree DisjointWith Course.
Mappings: Programme, Course.
Rules: hierarchies (disjointness propagation); clashes (sub/sub/disj, some/unsat)
Expected: unsat o1:Programme, o2:Programme and o1:Student; blame Programme and Course for each.
Why: Programme is a Course in o1 and a Degree in o2, and Degree excludes Course, so Programme is empty on both sides, and because every Student must be enrolled in a Programme, Student is empty too, which a hierarchy-only projection would not notice.

### w6 — a nested filler that needs HermiT

o1: Author SubClassOf writes some (Book and publishedBy some Publisher); Book SubClassOf Document.
o2: Author SubClassOf writes only Article; Book DisjointWith Article.
Mappings: Author, Book, Document, writes.
Rules: HermiT normalisation; then as w1
Expected: the identity normaliser refuses the nested filler with a message naming it; with --normaliser hermit, unsat o1:Author and o2:Author, blame Author, Book, writes.
Why: HermiT names the nested filler internal:def#0 and records def#0 SubClassOf Book, so the existential on Author inherits Book as a filler and the w1 argument goes through unchanged.

## Clash Rules and Variations

The following fixtures mirror the worked examples presented within the preliminary report "Restriction-essential Ontology Alignment Repair" under the Section "Examples of Restriction-essential Cases". The fixture name gives the rule and the premise it exercises. The `expected.json` file for each of these was confirmed by HermiT (`tests/test_reasoner.py`). Specifically, the unsatisfiable classes agree, every blamed mapping's removal restores coherence, and no unblamed mapping's removal does. `Rules:` lines name the rules of `rules/repair.dl`. The actual ontologies can be viewed under [tests/witnesses](tests/witnesses/) directory.

### d1_role — Some–All clash (D1, via role inclusion)

o1: Author SubClassOf publishes some Book; publishes SubPropertyOf writes.
o2: Author SubClassOf writes only Article; Book DisjointWith Article.
Mappings: Author, writes, Book.
Rules: S1 (property up); S2 (inherited); D1
Expected: unsat o1:Author and o2:Author; blame all three.
Why: A published book is a written book by the role inclusion, and o2 lets an author write only articles.

### d1_filler — Some–All clash (D1, via filler inclusion)

o1: Monograph SubClassOf Book; Author SubClassOf writes some Monograph.
o2: Author SubClassOf writes only Article; Book DisjointWith Article.
Mappings: Author, writes, Book.
Rules: S1 (filler up); disjointness inherited; D1
Expected: unsat o1:Author and o2:Author; blame all three.
Why: Monograph is disjoint from Article only through Monograph SubClassOf Book, which the closure supplies.

### d1_subject — Some–All clash (D1, via filler and subject inclusion)

o1: BiographicalAuthor SubClassOf Author; Biography SubClassOf Book; BiographicalAuthor SubClassOf writes some Biography.
o2: Author SubClassOf writes only Article; Book DisjointWith Article.
Mappings: Author, writes, Book.
Rules: S1 (filler up); S2 (inherited by subclass); D1
Expected: unsat o1:BiographicalAuthor only; blame all three.
Why: The unsatisfiable class has no mapping of its own; it inherits the universal from Author and the existential is its own.

### d2_base — Min–Max clash (D2, base)

o1: Paper SubClassOf hasReviewer max 1.
o2: Paper SubClassOf hasReviewer min 2.
Mappings: Paper, hasReviewer.
Rules: D2 with every premise trivial
Expected: unsat o1:Paper and o2:Paper; blame both.
Why: No disjointness axiom exists anywhere; the projection of this pair has no False-headed clause at all.

### d2_role — Min–Max clash (D2, via role inclusion)

o1: Paper SubClassOf hasReviewer max 1.
o2: Paper SubClassOf hasSeniorReviewer min 2; hasSeniorReviewer SubPropertyOf hasReviewer.
Mappings: Paper, hasReviewer.
Rules: S1 (property up); D2
Expected: unsat o1:Paper and o2:Paper; blame both.
Why: Two senior reviewers are two reviewers; the lower bound sits on the sub-property, the cap on the super-property.

### d3_base — Functional merge clash (D3, base)

o1: Paper SubClassOf hasCorrespondingAuthor some Student; hasCorrespondingAuthor Functional.
o2: Paper SubClassOf hasCorrespondingAuthor some Faculty; Student DisjointWith Faculty.
Mappings: Paper, hasCorrespondingAuthor, Student.
Rules: functionality on Thing (S3 inherited); D3
Expected: unsat o1:Paper and o2:Paper; blame all three.
Why: One functional property, two forced successors in disjoint classes; functionality makes them one individual.

### d3_role — Functional merge clash (D3, via role inclusion)

o1: StudentPaper SubClassOf Paper; StudentPaper SubClassOf submittedBy some Student; submittedBy SubPropertyOf hasSubmitter; hasSubmitter Functional.
o2: Paper SubClassOf hasCorrespondingAuthor some Faculty; hasCorrespondingAuthor SubPropertyOf hasSubmitter; Student DisjointWith Faculty.
Mappings: Paper, hasSubmitter, Student.
Rules: S1 (property up, both sides); functionality on Thing; D3
Expected: unsat o1:StudentPaper only; blame all three.
Why: Two distinct sub-properties of a functional common super-property; Paper itself stays satisfiable.

### d4_base — Functionality violation (D4, base)

o1: hasReviewer Functional.
o2: Paper SubClassOf hasReviewer min 2.
Mappings: hasReviewer only.
Rules: functionality on Thing; D2 with the Thing cap inherited (D4)
Expected: unsat o2:Paper; blame the property mapping.
Why: The only removable cause is a property mapping; no class mapping exists.

### d4_role — Functionality violation (D4, via role inclusion)

o1: hasReviewer Functional.
o2: Paper SubClassOf hasLeadReviewer min 2; hasLeadReviewer SubPropertyOf hasReviewer.
Mappings: hasReviewer only.
Rules: S3 (property down, functionality inherited); D4
Expected: unsat o2:Paper; blame the property mapping.
Why: Functionality of hasReviewer is inherited by hasLeadReviewer.

### d5_base — Range violation (D5, base)

o1: hasReviewer Range PCMember.
o2: Paper SubClassOf hasReviewer some External; External DisjointWith PCMember.
Mappings: hasReviewer, PCMember.
Rules: range on Thing (S2 inherited); D1 (D5)
Expected: unsat o2:Paper; blame both.
Why: The forced external reviewer must be a PC member by the range.

### d5_role — Range violation (D5, via role inclusion)

o1: hasReviewer Range PCMember.
o2: Paper SubClassOf hasExternalReviewer some External; hasExternalReviewer SubPropertyOf hasReviewer; External DisjointWith PCMember.
Mappings: hasReviewer, PCMember.
Rules: S2 (property down, range inherited); D5
Expected: unsat o2:Paper; blame both.
Why: The range reaches the sub-property through the role inclusion and the property mapping.

### d5_filler — Range violation (D5, via filler inclusion)

o1: hasReviewer Range PCMember.
o2: Paper SubClassOf hasReviewer some IndustryReviewer; IndustryReviewer SubClassOf External; External DisjointWith PCMember.
Mappings: hasReviewer, PCMember.
Rules: disjointness inherited; D5
Expected: unsat o2:Paper; blame both.
Why: IndustryReviewer is disjoint from PCMember only through the class closure.

### s1_definition — Derived lower bound (S1)

o1: Paper SubClassOf hasReviewer min 2.
o2: Reviewed EquivalentTo hasReviewer some Thing; Unreviewed SubClassOf Paper; Unreviewed DisjointWith Reviewed.
Mappings: Paper, hasReviewer.
Rules: S1 numeric (min 2 reaches some); atleastLHS bridge; named disjointness
Expected: unsat o2:Unreviewed; blame both.
Why: No clash rule fires; the definition carries the restriction to a named class and the named disjointness does the rest.

### s1_domain — Domain-axiom chain (S1; the paper's W7 shape)

o1: MilitaryAsset SubClassOf DefenceAsset; MilitaryAsset SubClassOf deployed some Location.
o2: Software DisjointWith DefenceAsset; deployed Domain Software.
Mappings: DefenceAsset, deployed.
Rules: S1 (filler up to Thing, property through the mapping); someLHS bridge from the domain axiom; named disjointness
Expected: unsat o1:MilitaryAsset; blame both.
Why: The disjointness is named and in the projection; only the path to it is restriction-mediated.

### s2_definition — Derived universal (S2)

o1: Paper SubClassOf hasReviewer only SeniorPC; SeniorPC SubClassOf PCMember.
o2: PCReviewed EquivalentTo hasReviewer only PCMember; StudentTrackPaper SubClassOf Paper; StudentTrackPaper DisjointWith PCReviewed.
Mappings: Paper, hasReviewer, PCMember.
Rules: S2 (filler up, property down); onlyLHS bridge; named disjointness
Expected: unsat o2:StudentTrackPaper; blame all three.
Why: All reviewers senior PC implies all reviewers PC, which is the defined class.

### s3_definition — Derived upper bound (S3)

o1: Paper SubClassOf hasReviewer max 1.
o2: LightlyReviewed EquivalentTo hasReviewer max 2; ConferencePaper SubClassOf Paper; ConferencePaper DisjointWith LightlyReviewed.
Mappings: Paper, hasReviewer.
Rules: S3 numeric (max 1 reaches max 2); atmostLHS bridge; named disjointness
Expected: unsat o2:ConferencePaper; blame both.
Why: At most one reviewer is at most two, which is the defined class.
