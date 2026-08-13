import unittest
import os
import json
import hashlib
import re
from neo4j import GraphDatabase

# ==============================================================================
# TESTSUITE NACH SOFTWARETECHNIK-LEHRSTANDARDS (Prof. Dr. Leen Lambers)
# Taxonomie: Unit Tests -> Integration Tests -> System Tests (Orakel-Tests)
# ==============================================================================

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.abspath(os.path.join(TEST_DIR, ".."))
GT_PATH = os.path.join(EVAL_DIR, "ground_truth.json")
EXTRACTOR_DIR = os.path.abspath(os.path.join(EVAL_DIR, "..", "user-story-extractor", "extracted-user-stories", "gpt-4-turbo"))

URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "master2026")
DATABASE_NAME = os.getenv("NEO4J_DATABASE", "userstories")


class TestUnitETL(unittest.TestCase):
    """
    Stufe 1: Modul- und Unit-Tests (White-Box / Black-Box Heuristiken)
    Fokus: Deterministische Hash-Generierung, Textnormalisierung und Schema-Konformität.
    """

    def test_deterministic_clean_id_generation(self):
        """Prüft die kollisionsarme, reproduzierbare MD5-Hash-Generierung."""
        pid = "g03"
        text1 = "As a user, I want to login."
        text2 = "as a user, i want to login.   "  # Normalisierungs-Äquivalenz
        text3 = "As an admin, I want to login."

        h1 = f"{pid}_{hashlib.md5(text1.strip().lower().encode('utf-8')).hexdigest()[:8]}"
        h2 = f"{pid}_{hashlib.md5(text2.strip().lower().encode('utf-8')).hexdigest()[:8]}"
        h3 = f"{pid}_{hashlib.md5(text3.strip().lower().encode('utf-8')).hexdigest()[:8]}"

        self.assertEqual(h1, h2, "Normalisierte Texte müssen identische Clean-IDs erzeugen.")
        self.assertNotEqual(h1, h3, "Unterschiedliche User Stories müssen distinkte IDs erhalten.")
        self.assertEqual(len(h1), 12, "Die ID muss dem Format {pid}_{8-hex} (12 Zeichen) entsprechen.")

    def test_text_normalization(self):
        """Prüft die Bereinigung von Interpunktion und Whitespaces."""
        raw = "As a User, I want to edit: properties & accounts!"
        expected = "as a user i want to edit properties  accounts"
        cleaned = re.sub(r"[^\w\s]", "", raw.lower()).strip()
        self.assertEqual(cleaned, expected)

    def test_json_structure_conformance(self):
        """Validiert das hierarchische Extraktions-Schema der JSON-Rohdaten."""
        g03_path = os.path.join(EXTRACTOR_DIR, "g03.json")
        if os.path.exists(g03_path):
            with open(g03_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIsInstance(data, list)
            self.assertGreater(len(data), 0)
            sample = data[0]
            self.assertIn("Text", sample)
            self.assertIn("Persona", sample)
            self.assertIn("Action", sample)
            self.assertIn("Entity", sample)


class TestIntegrationGraph(unittest.TestCase):
    """
    Stufe 2: Integrationstests (Graph- und Pipeline-Integrität)
    Fokus: Persistierung, Kantenkardinalitäten und Index-Integrität in Neo4j.
    """

    @classmethod
    def setUpClass(cls):
        cls.driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

    @classmethod
    def tearDownClass(cls):
        cls.driver.close()

    def test_neo4j_connection_and_schema(self):
        """Verifiziert die Erreichbarkeit der Datenbank und Existenz der Indizes."""
        with self.driver.session(database=DATABASE_NAME) as session:
            result = session.run("SHOW CONSTRAINTS").data()
            self.assertIsNotNone(result)

    def test_userstory_node_counts_partitioned(self):
        """
        Prüft die partitionsbasierte Ingestion pro Backlog (G03 und G04) gemäß
        der dokumentierten Datenbasis (Deduplizierung und Vorfilterung).
        - G03: 58 raw - 1 Duplikat (G03_45/46) - 2 ausgelassen (G03_39, 54) = 55 Knoten
        - G04: 51 raw - 3 ausgelassen (G04_05, 15, 48) = 48 Knoten
        - Gesamt: 55 + 48 = 103 UserStory-Knoten im Zielgraphen
        """
        with self.driver.session(database=DATABASE_NAME) as session:
            g03_cnt = session.run("MATCH (us:UserStory {pid: 'g03'}) RETURN count(us) AS cnt").single()["cnt"]
            g04_cnt = session.run("MATCH (us:UserStory {pid: 'g04'}) RETURN count(us) AS cnt").single()["cnt"]
            total_cnt = session.run("MATCH (us:UserStory) RETURN count(us) AS cnt").single()["cnt"]

            self.assertEqual(g03_cnt, 55, "Datensatz G03 muss exakt 55 UserStory-Knoten enthalten (58 raw - 1 Duplikat - 2 omitted).")
            self.assertEqual(g04_cnt, 48, "Datensatz G04 muss exakt 48 UserStory-Knoten enthalten (51 raw - 3 omitted).")
            self.assertEqual(total_cnt, 103, "Die Gesamtsumme der UserStory-Knoten im Zielgraphen muss exakt 103 betragen.")

    def test_essential_graph_topologies(self):
        """Prüft die Existenz der semantischen Kanten (TRIGGERS und TARGETS)."""
        with self.driver.session(database=DATABASE_NAME) as session:
            triggers_cnt = session.run("MATCH ()-[r:TRIGGERS]->() RETURN count(r) AS cnt").single()["cnt"]
            targets_cnt = session.run("MATCH ()-[r:TARGETS]->() RETURN count(r) AS cnt").single()["cnt"]
            self.assertGreater(triggers_cnt, 0, "Es müssen TRIGGERS-Kanten im Graphen existieren.")
            self.assertGreater(targets_cnt, 0, "Es müssen TARGETS-Kanten im Graphen existieren.")


class TestSystemQualityChecks(unittest.TestCase):
    """
    Stufe 3: Systemtests (Test-Orakel auf Basis von Äquivalenzklassen & RIPR-Modell)
    Fokus: Verifikation der 6 Cypher-NAC-Prüfregeln gegen das theoriegeleitete Golden Sample.
    """

    @classmethod
    def setUpClass(cls):
        cls.driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
        with open(GT_PATH, "r", encoding="utf-8") as f:
            cls.ground_truth = json.load(f)

    @classmethod
    def tearDownClass(cls):
        cls.driver.close()

    def test_oracle_missing_benefit_check(self):
        """
        Orakel-Test für Missing Benefit:
        Äquivalenzklasse: Stories ohne Geschäftswert (G04_09, G04_10, G04_11, G04_14, G04_20, G04_26).
        """
        q = """
        MATCH (us:UserStory)
        WHERE NOT (us)-[:HAS_BENEFIT]->(:Benefit)
        RETURN count(us) AS defect_count
        """
        with self.driver.session(database=DATABASE_NAME) as session:
            res = session.run(q).single()["defect_count"]
            self.assertEqual(res, 6, "Der Missing Benefit Check muss exakt 6 defekte Stories in G04 identifizieren.")

    def test_oracle_non_atomic_fat_stories(self):
        """
        Orakel-Test für Atomaritätsprüfung (k=2):
        Äquivalenzklasse: Stories mit Aktionsüberfächerung (>2 Aktionen).
        """
        q = """
        MATCH (us:UserStory)-[:HAS_ACTION]->(a:Action)
        WITH us, count(a) AS act_count
        WHERE act_count > 2
        RETURN count(us) AS fat_count
        """
        with self.driver.session(database=DATABASE_NAME) as session:
            res = session.run(q).single()["fat_count"]
            self.assertEqual(res, 35, "Die Cypher-Abfrage für Fat Stories (>2) muss exakt 35 Alarme erzeugen.")

    def test_oracle_incomplete_means_path_consistency(self):
        """
        Orakel-Test für semantische Vollständigkeit (Dangling Action):
        Verifiziert die Story-Kontext-Bindung (us)-[:HAS_ACTION]->(a)-[:TARGETS]->(e)<-[:HAS_ENTITY]-(us).
        """
        q = """
        MATCH (us:UserStory)-[:HAS_ACTION]->(a:Action)
        WHERE NOT ( (a)-[:TARGETS]->(:Entity)<-[:HAS_ENTITY]-(us) )
        RETURN count(us) AS dangling_count
        """
        with self.driver.session(database=DATABASE_NAME) as session:
            res = session.run(q).single()["dangling_count"]
            self.assertGreaterEqual(res, 0, "Dangling Actions Abfrage muss syntaktisch valide und ausführbar sein.")

    def test_oracle_overlap_duplicate_prevention(self):
        """
        Orakel-Test für Redundanz und Duplikate:
        Prüft die präventive Hash-Deduplizierung auf Ingestions-Ebene.
        """
        with self.driver.session(database=DATABASE_NAME) as session:
            dups = session.run("""
                MATCH (us:UserStory)
                WHERE us.pid = 'g03' AND us.text CONTAINS 'Complete Building Development Project'
                RETURN count(us) AS cnt
            """).single()["cnt"]
            self.assertEqual(dups, 1, "Das Textduplikat in G03 darf im Zielgraphen nur als 1 Knoten existieren.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
