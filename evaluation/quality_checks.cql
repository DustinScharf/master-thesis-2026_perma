// ==============================================================================
// MASTERARBEIT: CYPHER QUALITY ASSURANCE QUERIES
// Graph-based Quality Checks for User Story Backlogs
// ==============================================================================

// ------------------------------------------------------------------------------
// 1. INTRA-STORY CHECKS (Mikroebene)
// ------------------------------------------------------------------------------

// A. Strukturelle Wohlgeformtheit (Well-formedness / Triad Check)
// Identifiziert User Stories, denen mindestens eine der Komponenten
// (Persona, Action, Entity) fehlt.
MATCH (us:UserStory)
WHERE NOT (us)-[:HAS_PERSONA]->(:Persona)
   OR NOT (us)-[:HAS_ACTION]->(:Action)
   OR NOT (us)-[:HAS_ENTITY]->(:Entity)
RETURN us.id AS Story_ID, us.pid AS Project, us.text AS Text;

// B. Fehlender Geschäftswert (Missing Benefit / Unmotivated Requirement)
// Findet Stories ohne ausgehende HAS_BENEFIT-Kante.
MATCH (us:UserStory)
WHERE NOT (us)-[:HAS_BENEFIT]->(:Benefit)
RETURN us.id AS Story_ID, us.pid AS Project, us.text AS Text;

// C. Atomaritätsprüfung (Non-Atomic / Fat Story Check)
// Erkennt aggregierte Stories mit mehr als 2 Aktionen (Schwellenwert k=2).
MATCH (us:UserStory)-[:HAS_ACTION]->(a:Action)
WITH us, count(DISTINCT a) AS action_count, collect(DISTINCT a.name) AS actions
WHERE action_count > 2
RETURN us.id AS Story_ID, us.pid AS Project, action_count, actions, us.text AS Text
ORDER BY action_count DESC;

// D. Semantische Vollständigkeit des Handlungsziels (Incomplete Means / Dangling Action)
// Erkennt Aktionen innerhalb einer Story, die nicht auf eine der Story-Entitäten einwirken.
MATCH (us:UserStory)-[:HAS_ACTION]->(a:Action)
WHERE NOT ( (a)-[:TARGETS]->(:Entity)<-[:HAS_ENTITY]-(us) )
RETURN us.id AS Story_ID, us.pid AS Project, a.name AS Dangling_Action, us.text AS Text;


// ------------------------------------------------------------------------------
// 2. INTER-STORY CHECKS (Makroebene)
// ------------------------------------------------------------------------------

// A. Eindeutigkeit & Funktionale Redundanz (Overlap Check)
// Erkennt Stories, die dieselbe (Action -> TARGETS -> Entity)-Operation anfordern.
MATCH (us1:UserStory)-[:HAS_ACTION]->(a:Action)-[:TARGETS]->(e:Entity),
      (us1)-[:HAS_ENTITY]->(e),
      (us2:UserStory)-[:HAS_ACTION]->(a),
      (us2)-[:HAS_ENTITY]->(e)
WHERE us1.id < us2.id
RETURN DISTINCT us1.id AS Story_1, us2.id AS Story_2,
       a.name AS Action, e.name AS Entity;

// B. Cross-Persona Overlap Candidates (Review-Hinweis, kein formaler Konflikt)
// Erkennt verschiedene Rollen in verschiedenen Stories, die dieselbe Aktion
// auf demselben Objekt ausführen. Die Story-Mitgliedschaften begrenzen
// backlog-globale Fehlzuordnungen gemeinsam genutzter Knoten. Da die global
// harmonisierten semantischen Kanten keine Story-Provenienz speichern, ist das
// Ergebnis weiterhin ein Review-Kandidat und kein formaler Konfliktnachweis.
MATCH (us1:UserStory)-[:HAS_PERSONA]->(p1:Persona)-[:TRIGGERS]->(a:Action)-[:TARGETS]->(e:Entity),
      (us1)-[:HAS_ACTION]->(a),
      (us1)-[:HAS_ENTITY]->(e),
      (us2:UserStory)-[:HAS_PERSONA]->(p2:Persona)-[:TRIGGERS]->(a),
      (us2)-[:HAS_ACTION]->(a),
      (us2)-[:HAS_ENTITY]->(e)
WHERE us1.id < us2.id AND p1 <> p2
RETURN DISTINCT us1.id AS Story_1, us2.id AS Story_2,
       p1.name AS Persona_1, p2.name AS Persona_2,
       a.name AS Action, e.name AS Target_Entity;
