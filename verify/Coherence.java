import java.io.File;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;

import org.semanticweb.HermiT.Reasoner;
import org.semanticweb.owlapi.apibinding.OWLManager;
import org.semanticweb.owlapi.model.*;

/**
 * HermiT cross-check for a witness pair.
 *
 *   java --add-opens java.base/java.lang=ALL-UNNAMED -cp normaliser/target/normaliser.jar verify/Coherence.java O1 O2 ALIGNMENT.tsv [--without ID ...]
 *
 * Loads both ontologies, adds one EquivalentClasses / EquivalentObjectProperties axiom per mapping
 * in ALIGNMENT.tsv (as written by hornrepair.matcher.write_alignment), except the ids named after
 * --without, classifies with HermiT and prints one unsatisfiable named class per line.
 * A first line "o1-coherent: true/false" and "o2-coherent: true/false" reports each input alone.
 */
public class Coherence {
    public static void main(String[] args) throws Exception {
        OWLOntologyManager m = OWLManager.createOWLOntologyManager();
        OWLDataFactory df = m.getOWLDataFactory();
        OWLOntology o1 = m.loadOntologyFromOntologyDocument(new File(args[0]));
        OWLOntology o2 = m.loadOntologyFromOntologyDocument(new File(args[1]));
        Set<String> without = new HashSet<>();
        for (int i = 4; i < args.length; i++) without.add(args[i]);

        System.out.println("o1-coherent: " + unsat(m, df, o1.getAxioms()).isEmpty());
        System.out.println("o2-coherent: " + unsat(m, df, o2.getAxioms()).isEmpty());

        Set<OWLAxiom> axioms = new HashSet<>(o1.getAxioms());
        axioms.addAll(o2.getAxioms());
        List<String> lines = Files.readAllLines(Paths.get(args[2]));
        for (String line : lines.subList(1, lines.size())) {
            if (line.trim().isEmpty()) continue;
            String[] f = line.split("\t");
            String id = f[4] + ":" + f[0] + "|" + f[1];
            if (without.contains(id)) continue;
            if (f[4].equals("class")) {
                axioms.add(df.getOWLEquivalentClassesAxiom(df.getOWLClass(IRI.create(f[0])), df.getOWLClass(IRI.create(f[1]))));
            } else {
                axioms.add(df.getOWLEquivalentObjectPropertiesAxiom(df.getOWLObjectProperty(IRI.create(f[0])), df.getOWLObjectProperty(IRI.create(f[1]))));
            }
        }
        for (String c : unsat(m, df, axioms)) System.out.println(c);
    }

    static List<String> unsat(OWLOntologyManager m, OWLDataFactory df, Set<OWLAxiom> axioms) throws Exception {
        OWLOntology merged = m.createOntology(axioms);
        Reasoner r = new Reasoner(new org.semanticweb.HermiT.Configuration(), merged);
        List<String> out = new ArrayList<>();
        for (OWLClass c : r.getUnsatisfiableClasses().getEntitiesMinusBottom()) out.add(c.getIRI().toString());
        r.dispose();
        m.removeOntology(merged);
        Collections.sort(out);
        return out;
    }
}
