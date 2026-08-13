import json
import os
import hashlib
from neo4j import GraphDatabase

# ==============================================================================
# NATIVER ETL-IMPORT: JSON-ROHDATEN -> NEO4J GRAPH-DATENBANK
# ==============================================================================

URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "master2026")
DATABASE_NAME = os.getenv("NEO4J_DATABASE", "userstories")

EXPERIMENT_NAME = "gpt-4-turbo"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXTRACTOR_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "user-story-extractor", "extracted-user-stories", EXPERIMENT_NAME))

CYPHER_IMPORT_QUERY = """
UNWIND $stories AS story
MERGE (us:UserStory {id: story.Clean_ID, model: $model_name})
SET us.text = COALESCE(story.Text, ""),
    us.name = COALESCE(story.Text, ""),
    us.pid = COALESCE(story.PID, "UNKNOWN_PID")

WITH story, us
FOREACH (bName IN CASE WHEN story.Benefit IS NOT NULL AND trim(story.Benefit) <> "" THEN [story.Benefit] ELSE [] END |
    MERGE (b:Benefit {name: bName})
    MERGE (us)-[:HAS_BENEFIT]->(b)
)

WITH story, us
FOREACH (pName IN CASE WHEN story.Persona IS NOT NULL AND size(story.Persona) > 0 THEN story.Persona ELSE [] END |
    MERGE (p:Persona {name: pName})
    MERGE (us)-[:HAS_PERSONA]->(p)
)

WITH story, us
FOREACH (aName IN CASE WHEN story.Action IS NOT NULL AND story.Action.`Primary Action` IS NOT NULL THEN story.Action.`Primary Action` ELSE [] END |
    MERGE (a:Action {name: aName})
    MERGE (us)-[:HAS_ACTION]->(a)
)

WITH story, us
FOREACH (eName IN CASE WHEN story.Entity IS NOT NULL AND story.Entity.`Primary Entity` IS NOT NULL THEN story.Entity.`Primary Entity` ELSE [] END |
    MERGE (e:Entity {name: eName})
    MERGE (us)-[:HAS_ENTITY]->(e)
)

WITH story, us
FOREACH (trigger IN CASE WHEN story.Triggers IS NOT NULL THEN story.Triggers ELSE [] END |
    MERGE (p:Persona {name: trigger[0]})
    MERGE (a:Action {name: trigger[1]})
    MERGE (p)-[:TRIGGERS]->(a)
    MERGE (us)-[:HAS_PERSONA]->(p)
    MERGE (us)-[:HAS_ACTION]->(a)
)

WITH story, us
FOREACH (target IN CASE WHEN story.Targets IS NOT NULL THEN story.Targets ELSE [] END |
    MERGE (a:Action {name: target[0]})
    MERGE (e:Entity {name: target[1]})
    MERGE (a)-[:TARGETS]->(e)
    MERGE (us)-[:HAS_ACTION]->(a)
    MERGE (us)-[:HAS_ENTITY]->(e)
)
"""

def generate_clean_id(pid: str, text: str) -> str:
    """Erzeugt eine deterministische 8-stellige ID auf Basis des Textes."""
    h = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
    return f"{pid}_{h}"

def import_backlogs():
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    target_files = [
        ("g03", "g03.json", "g03_gpt-4-turbo_intersecting.json"),
        ("g04", "g04.json", "g04_gpt-4-turbo_intersecting.json")
    ]
    
    with driver.session(database=DATABASE_NAME) as session:
        print(f"[*] Initialisiere Schema-Constraints und Indizes auf '{DATABASE_NAME}'...")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (u:UserStory) REQUIRE u.id IS UNIQUE")
        session.run("CREATE INDEX IF NOT EXISTS FOR (p:Persona) ON (p.name)")
        session.run("CREATE INDEX IF NOT EXISTS FOR (a:Action) ON (a.name)")
        session.run("CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.name)")
        session.run("CREATE INDEX IF NOT EXISTS FOR (b:Benefit) ON (b.name)")

        total_imported = 0
        for pid, fname_std, fname_int in target_files:
            p1 = os.path.join(EXTRACTOR_DIR, fname_std)
            p2 = os.path.join(EXTRACTOR_DIR, fname_int)
            fpath = p1 if os.path.exists(p1) else p2
            
            if not os.path.exists(fpath):
                print(f"[!] Warnung: Datei {fpath} nicht gefunden.")
                continue
                
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            enriched = []
            for item in data:
                txt = item.get("Text", "")
                item["PID"] = pid
                item["Clean_ID"] = generate_clean_id(pid, txt)
                enriched.append(item)
                
            session.run(CYPHER_IMPORT_QUERY, stories=enriched, model_name=EXPERIMENT_NAME)
            print(f"[+] Datensatz {pid} ({len(enriched)} Stories aus {os.path.basename(fpath)}) erfolgreich via Cypher importiert.")
            total_imported += len(enriched)

        print(f"\n[OK] ETL-Import abgeschlossen: Insgesamt {total_imported} User Stories in Neo4j geladen.")
    driver.close()

if __name__ == "__main__":
    import_backlogs()
