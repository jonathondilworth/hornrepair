/* Copyright 2008, 2009, 2010 by the Oxford University Computing Laboratory

   This file is part of HermiT.

   HermiT is free software: you can redistribute it and/or modify
   it under the terms of the GNU Lesser General Public License as published by
   the Free Software Foundation, either version 3 of the License, or
   (at your option) any later version.

   HermiT is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU Lesser General Public License for more details.

   You should have received a copy of the GNU Lesser General Public License
   along with HermiT.  If not, see <http://www.gnu.org/licenses/>.
*/
package org.semanticweb.HermiT.structural;

import java.util.Collection;

import org.semanticweb.owlapi.model.OWLClassExpression;
import org.semanticweb.owlapi.model.OWLObjectPropertyExpression;

/**
 * OWLAxioms. See: org.semanticweb.HermiT.structural.OWLAxioms
 * Source: org.semanticweb.hermit-1.3.8.413.jar
 * OWLAxiomsAdapted
 */

public class OWLAxiomsAdapted extends OWLAxioms {
    
  public OWLAxiomsAdapted() {}
    
  public Collection<OWLClassExpression[]> getNormalisedConceptInclusions() {
    return m_conceptInclusions;
  }

  public Collection<OWLObjectPropertyExpression[]> getNormalisedObjectPropertyInclusions() {
    return m_simpleObjectPropertyInclusions;
  }

}