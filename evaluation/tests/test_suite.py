import unittest
import os
import json
import hashlib
import re
from neo4j import GraphDatabase

# ==============================================================================
# TESTSUITE: Unit Tests -> Integration Tests -> System Tests (Orakel-Tests)
# ==============================================================================

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.abspath(os.path.join(TEST_DIR, ".."))
GT_PATH = os.path.join(EVAL_DIR, "ground_truth.json")
EXTRACTOR_DIR = os.path.join(EVAL_DIR, "extracted_data", "gpt-4-turbo")

URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD")
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
        text1_duplicate = "As a user, I want to login."
        text2 = "as a user, i want to login.   "
        text3 = "As an admin, I want to login."

        h1 = f"{pid}_{hashlib.md5(text1.encode('utf-8')).hexdigest()[:8]}"
        h1_duplicate = f"{pid}_{hashlib.md5(text1_duplicate.encode('utf-8')).hexdigest()[:8]}"
        h2 = f"{pid}_{hashlib.md5(text2.encode('utf-8')).hexdigest()[:8]}"
        h3 = f"{pid}_{hashlib.md5(text3.encode('utf-8')).hexdigest()[:8]}"

        self.assertEqual(
            h1,
            h1_duplicate,
            "Exakte Textduplikate müssen identische Clean-IDs erzeugen.",
        )
        self.assertNotEqual(
            h1,
            h2,
            "Der produktive Hash arbeitet bewusst auf dem unveränderten Text.",
        )
        self.assertNotEqual(h1, h3, "Unterschiedliche User Stories müssen distinkte IDs erhalten.")
        self.assertEqual(
            len(h1),
            12,
            "Die ID muss dem Format {pid}_{8-hex} (12 Zeichen) entsprechen.",
        )

    def test_text_normalization(self):
        """Prüft die Bereinigung von Interpunktion und Whitespaces."""
        raw = "As a User, I want to edit: properties & accounts!"
        expected = "as a user i want to edit properties  accounts"
        cleaned = re.sub(r"[^\w\s]", "", raw.lower()).strip()
        self.assertEqual(cleaned, expected)

    def test_json_structure_conformance(self):
        """Validiert das hierarchische Extraktions-Schema der JSON-Rohdaten."""
        g03_path = os.path.join(EXTRACTOR_DIR, "g03.json")
        self.assertTrue(os.path.exists(g03_path), f"Extraktionsdatei fehlt: {g03_path}")
        with open(g03_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        required_keys = {"Text", "Persona", "Action", "Entity"}
        for index, story in enumerate(data, start=1):
            self.assertTrue(
                required_keys.issubset(story),
                f"Story {index} verletzt das Extraktionsschema.",
            )


class TestIntegrationGraph(unittest.TestCase):
    """
    Stufe 2: Integrationstests (Graph- und Pipeline-Integrität)
    Fokus: Persistierung, Kantenkardinalitäten und Index-Integrität in Neo4j.
    """

    @classmethod
    def setUpClass(cls):
        if not PASSWORD:
            raise RuntimeError("NEO4J_PASSWORD muss als Umgebungsvariable gesetzt sein.")
        cls.driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

    @classmethod
    def tearDownClass(cls):
        cls.driver.close()

    def test_neo4j_connection_and_schema(self):
        """Verifiziert Erreichbarkeit und UserStory-Eindeutigkeitsconstraint."""
        with self.driver.session(database=DATABASE_NAME) as session:
            count = session.run("""
                SHOW CONSTRAINTS YIELD labelsOrTypes, properties
                WHERE 'UserStory' IN labelsOrTypes AND properties = ['id']
                RETURN count(*) AS cnt
            """).single()["cnt"]
            self.assertGreaterEqual(
                count,
                1,
                "Der Eindeutigkeitsconstraint auf UserStory.id fehlt.",
            )

    def test_userstory_node_counts_partitioned(self):
        """
        Prüft die partitionsbasierte Ingestion pro Backlog (G03 und G04) gemäß
        der dokumentierten Datenbasis (Deduplizierung und Vorfilterung).
        - G03: 58 raw - 1 Duplikat (G03_45/46) - 2 ausgelassen (G03_39, 54) = 55 Knoten
        - G04: 51 raw - 3 ausgelassen (G04_05, 15, 48) = 48 Knoten
        - Gesamt: 55 + 48 = 103 UserStory-Knoten im Zielgraphen
        """
        with self.driver.session(database=DATABASE_NAME) as session:
            g03_cnt = session.run(
                "MATCH (us:UserStory {pid: 'g03'}) RETURN count(us) AS cnt"
            ).single()["cnt"]
            g04_cnt = session.run(
                "MATCH (us:UserStory {pid: 'g04'}) RETURN count(us) AS cnt"
            ).single()["cnt"]
            total_cnt = session.run("MATCH (us:UserStory) RETURN count(us) AS cnt").single()["cnt"]

            self.assertEqual(
                g03_cnt,
                55,
                "G03 muss 55 Knoten enthalten (58 raw - 1 Duplikat - 2 omitted).",
            )
            self.assertEqual(
                g04_cnt,
                48,
                "G04 muss 48 Knoten enthalten (51 raw - 3 omitted).",
            )
            self.assertEqual(
                total_cnt,
                103,
                "Der Zielgraph muss insgesamt exakt 103 UserStory-Knoten enthalten.",
            )

    def test_essential_graph_topologies(self):
        """Prüft die experimentell dokumentierten Kantenkardinalitäten."""
        with self.driver.session(database=DATABASE_NAME) as session:
            triggers_cnt = session.run(
                "MATCH ()-[r:TRIGGERS]->() RETURN count(r) AS cnt"
            ).single()["cnt"]
            targets_cnt = session.run(
                "MATCH ()-[r:TARGETS]->() RETURN count(r) AS cnt"
            ).single()["cnt"]
            self.assertEqual(
                triggers_cnt,
                126,
                "Der Zielgraph muss exakt 126 TRIGGERS-Kanten enthalten.",
            )
            self.assertEqual(
                targets_cnt,
                401,
                "Der Zielgraph muss exakt 401 TARGETS-Kanten enthalten.",
            )


class TestSystemQualityChecks(unittest.TestCase):
    """
    Stufe 3: Systemtests (Test-Orakel auf Basis von Äquivalenzklassen)
    Fokus: Verifikation von vier Kernregeln gegen das theoriegeleitete Golden Sample.
    """

    @classmethod
    def setUpClass(cls):
        if not PASSWORD:
            raise RuntimeError("NEO4J_PASSWORD muss als Umgebungsvariable gesetzt sein.")
        cls.driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
        with open(GT_PATH, "r", encoding="utf-8") as f:
            cls.ground_truth = json.load(f)

    @classmethod
    def tearDownClass(cls):
        cls.driver.close()

    def test_oracle_missing_benefit_check(self):
        """
        Orakel-Test für Missing Benefit:
        Äquivalenzklasse: Stories ohne Geschäftswert
        (G04_09, G04_10, G04_11, G04_14, G04_20, G04_26).
        """
        q = """
        MATCH (us:UserStory)
        WHERE NOT (us)-[:HAS_BENEFIT]->(:Benefit)
        RETURN count(us) AS defect_count
        """
        with self.driver.session(database=DATABASE_NAME) as session:
            res = session.run(q).single()["defect_count"]
            self.assertEqual(
                res,
                6,
                "Der Missing Benefit Check muss exakt 6 defekte Stories erkennen.",
            )

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
            self.assertEqual(
                res,
                35,
                "Die Cypher-Abfrage für Fat Stories (>2) muss 35 Alarme erzeugen.",
            )

    def test_oracle_incomplete_means_path_consistency(self):
        """
        Orakel-Test für semantische Vollständigkeit (Dangling Action):
        Verifiziert die story-gebundene Co-Membership
        (us)-[:HAS_ACTION]->(a)-[:TARGETS]->(e)<-[:HAS_ENTITY]-(us).
        Die globale TARGETS-Kante selbst speichert keine Story-Provenienz.
        """
        q = """
        MATCH (us:UserStory)-[:HAS_ACTION]->(a:Action)
        WHERE NOT ( (a)-[:TARGETS]->(:Entity)<-[:HAS_ENTITY]-(us) )
        RETURN count(DISTINCT us) AS dangling_count
        """
        with self.driver.session(database=DATABASE_NAME) as session:
            res = session.run(q).single()["dangling_count"]
            self.assertEqual(res, 2, "Der Dangling-Action-Check muss exakt zwei Alarme erzeugen.")

    def test_etl_duplicate_invariant(self):
        """
        Technische ETL-Invariante für exakte Textduplikate:
        Prüft die präventive Hash-Deduplizierung auf Importebene.
        Dies ist keine Klassifikationsausgabe des Graphsystems.
        """
        with self.driver.session(database=DATABASE_NAME) as session:
            dups = session.run("""
                MATCH (us:UserStory)
                WHERE us.pid = 'g03' AND us.text CONTAINS 'Complete Building Development Project'
                RETURN count(us) AS cnt
            """).single()["cnt"]
            self.assertEqual(
                dups,
                1,
                "Das Textduplikat in G03 darf nur als ein Knoten existieren.",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
