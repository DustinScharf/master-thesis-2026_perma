"""Pure tests plus optional read-only and rolled-back Neo4j integration tests.

Run pure tests: python -B -m unittest discover -s tests -p test_suite.py -v
Enable database tests only against imported REVIEW databases:
NEO4J_TEST_DATABASE_G03=g03; NEO4J_TEST_DATABASE_G04=g04;
NEO4J_URI=...; NEO4J_PASSWORD=...
Fixture writes live in transactions that are always rolled back. No deletion,
migration, or persisted modification of a real extraction partition is performed.
"""

import argparse
import copy
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
import uuid

EVAL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EVAL_DIR))

from evaluation_report import build_report, parse_aqusa, projected_predictions
from graph_model import (
    BACKLOGS, MODELS, aligned_ids, coverage, generate_clean_id, ground_truth_index,
    load_ground_truth, load_partition, load_partitions, metrics, normalize_text,
    prepare_partition, prepare_record, source_predictions, source_snapshot,
)
from graph_queries import QUERIES, standalone_cypher
from run_performance_evaluation import percentile, sum_db_hits
from import_to_neo4j import DEFAULT_DATABASE, database_for_backlog


def raw_story(text="Story A", actions=None, entities=None, targets=None, persona="user", triggers=None, benefit="useful"):
    actions = ["create"] if actions is None else actions
    entities = ["invoice"] if entities is None else entities
    return {
        "Text": text, "Persona": [persona] if persona else [],
        "Action": {"Primary Action": actions, "Secondary Action": []},
        "Entity": {"Primary Entity": entities, "Secondary Entity": []},
        "Targets": [] if targets is None else targets,
        "Triggers": [] if triggers is None else triggers,
        "Benefit": benefit,
    }


def fixture_partition(records, model="fixture", pid="g03"):
    return prepare_partition(records, model, pid)


class TestUnitModel(unittest.TestCase):
    def test_actual_id_helper_preserves_turbo_identity(self):
        partition = load_partition("gpt-4-turbo", "g03")
        story = next(r for r in partition["records"] if r["id"] == "g03_19e1d1f9")
        self.assertEqual(generate_clean_id("g03", story["text"]), "g03_19e1d1f9")
        self.assertNotEqual(generate_clean_id("g03", story["text"].strip()), story["id"])

    def test_prefix_only_removed_for_text_alignment(self):
        self.assertEqual(normalize_text("#G03# As a User, I want it."), normalize_text("As a User, I want it."))
        self.assertNotEqual(generate_clean_id("g03", "#G03# text"), generate_clean_id("g03", "text"))

    def test_primary_secondary_and_endpoints_are_united(self):
        raw = raw_story(actions=["A"], entities=["E"], targets=[["C", "G"]], triggers=[["other", "D"]])
        raw["Action"]["Secondary Action"] = ["B"]
        raw["Entity"]["Secondary Entity"] = ["F"]
        result = prepare_record(raw, "fixture", "g03")
        self.assertEqual(result["actions"], ["A", "B", "C", "D"])
        self.assertEqual(result["entities"], ["E", "F", "G"])
        self.assertEqual(result["personas"], ["other", "user"])

    def test_case_sensitive_concepts_are_not_renamed(self):
        raw = raw_story(actions=["Delete", "delete"], entities=["Invoice"], targets=[["Delete", "Invoice"]])
        part = fixture_partition([raw])
        self.assertEqual(part["records"][0]["actions"], ["Delete", "delete"])
        self.assertEqual(source_predictions(part)["dangling_actions"], {(part["records"][0]["id"], "delete")})

    def test_invalid_types_and_relation_pairs_are_rejected(self):
        examples = [
            {"Persona": "user"}, {"Targets": [["create"]]},
            {"Targets": [["", "invoice"]]}, {"Benefit": 7},
            {"Action": []}, {"Text": ""},
        ]
        for change in examples:
            with self.subTest(change=change):
                raw = raw_story()
                raw.update(change)
                with self.assertRaises(ValueError):
                    prepare_record(raw, "fixture", "g03")

    def test_every_supplied_model_backlog_file_is_validated(self):
        for model in MODELS:
            for pid in BACKLOGS:
                with self.subTest(model=model, pid=pid):
                    partition = load_partition(model, pid)
                    self.assertGreater(len(partition["records"]), 0)

    def test_repeated_fact_and_repeated_identical_record_are_sets(self):
        raw = raw_story(targets=[["create", "invoice"], ["create", "invoice"]])
        part = fixture_partition([raw, copy.deepcopy(raw)])
        self.assertEqual(part["duplicate_source_records"], 1)
        self.assertEqual(len(part["records"]), 1)
        self.assertEqual(len(part["records"][0]["targets"]), 1)

    def test_conflicting_extractions_of_identical_text_are_rejected(self):
        one, two = raw_story(), raw_story(benefit=None)
        with self.assertRaises(ValueError):
            fixture_partition([one, two])

    def test_gt_duplicate_mapping_retains_both_raw_ids(self):
        gt = load_ground_truth()
        index = ground_truth_index(gt)
        record = next(
            r for r in load_partition("gpt-4-turbo", "g03")["records"]
            if "Complete Building Development Project" in r["text"]
        )
        self.assertEqual(aligned_ids(record, index), {"G03_45", "G03_46"})

    def test_gt_mapping_is_backlog_specific_and_unknown_text_fails(self):
        gt = {
            "g03": [{"id": "A", "text": "same"}],
            "g04": [{"id": "B", "text": "same"}],
        }
        index = ground_truth_index(gt)
        record = prepare_record(raw_story(text="same"), "fixture", "g03")
        self.assertEqual(aligned_ids(record, index), {"A"})
        record["text"] = "unknown"
        with self.assertRaises(ValueError):
            aligned_ids(record, index)

    def test_coverage_counts_109_raw_and_103_canonical_stories(self):
        result = coverage(load_partitions("gpt-4-turbo"), load_ground_truth())
        self.assertEqual(result["reference_stories"], 109)
        self.assertEqual(result["canonical_graph_stories"], 103)
        self.assertEqual(result["represented_reference_stories"], 104)
        self.assertEqual(set(result["missing_reference_story_ids"]), {"G03_39", "G03_54", "G04_05", "G04_15", "G04_48"})

    def test_metrics_undefined_denominators_and_zero_f1(self):
        result = metrics(set(), {"A"})
        self.assertIsNone(result["Precision"])
        self.assertEqual(result["Recall"], 0.0)
        self.assertEqual(result["F1"], 0.0)
        empty = metrics(set(), set())
        self.assertIsNone(empty["Precision"])
        self.assertIsNone(empty["Recall"])
        self.assertIsNone(empty["F1"])

    def test_metrics_known_tp_fp_fn(self):
        result = metrics({"A", "B"}, {"A", "C", "D"})
        self.assertEqual((result["TP"], result["FP"], result["FN"]), (1, 1, 2))
        self.assertEqual((result["Precision"], result["Recall"], result["F1"]), (50.0, 33.33, 40.0))

    def test_aqusa_uses_explicit_story_number_for_duplicate(self):
        result = parse_aqusa(load_ground_truth())
        self.assertEqual(result["uniqueness"], {"G03_46"})
        self.assertEqual(result["incomplete_means"], {"G03_54"})

    def test_generated_cypher_matches_shared_queries(self):
        self.assertEqual((EVAL_DIR / "quality_checks.cql").read_text(encoding="utf-8").replace("\r\n", "\n"), standalone_cypher())

    def test_safe_new_database_default(self):
        self.assertEqual(DEFAULT_DATABASE, "userstories-review")
        shared = argparse.Namespace(database=DEFAULT_DATABASE, separate_databases=False)
        split = argparse.Namespace(database=DEFAULT_DATABASE, separate_databases=True)
        self.assertEqual(database_for_backlog(shared, "g03"), DEFAULT_DATABASE)
        self.assertEqual(database_for_backlog(split, "g03"), "g03")
        self.assertEqual(database_for_backlog(split, "g04"), "g04")

    def test_benchmark_helpers(self):
        self.assertEqual(percentile([1, 2, 3, 4], 0.95), 4)
        self.assertEqual(sum_db_hits({"args": {"DbHits": 2}, "children": [{"args": {"DbHits": 3}}]}), 5)

    def test_empty_database_skips_content_checks_but_checks_constraints(self):
        from graph_database import validate_schema
        runner = Mock()
        constraints, node_count = Mock(), Mock()
        constraints.data.return_value = []
        node_count.single.return_value = {"count": 0}
        runner.run.side_effect = [constraints, node_count]
        validate_schema(runner)
        self.assertEqual(runner.run.call_count, 2)
        self.assertTrue(runner.run.call_args_list[0].args[0].startswith("SHOW CONSTRAINTS"))
        self.assertEqual(runner.run.call_args_list[1].args[0], "MATCH (n) RETURN count(n) AS count")

    def test_empty_legacy_schema_is_still_rejected(self):
        from graph_database import validate_schema
        runner = Mock()
        runner.run.return_value.data.return_value = [{"labelsOrTypes": ["UserStory"], "properties": ["id"]}]
        with self.assertRaises(ValueError):
            validate_schema(runner)
        self.assertEqual(runner.run.call_count, 1)

    def test_nonempty_database_runs_all_content_checks(self):
        from graph_database import validate_schema
        runner = Mock()
        constraints = Mock()
        constraints.data.return_value = []
        responses = [constraints]
        for count in (1, 0, 0, 0):
            response = Mock()
            response.single.return_value = {"count": count}
            responses.append(response)
        runner.run.side_effect = responses
        validate_schema(runner)
        self.assertEqual(runner.run.call_count, 5)


class TestPureRuleReference(unittest.TestCase):
    def test_swapped_action_entity_pairs_do_not_overlap(self):
        part = fixture_partition([
            raw_story("A", ["delete", "create"], ["customer", "invoice"], [["delete", "customer"], ["create", "invoice"]]),
            raw_story("B", ["delete"], ["invoice"], [["delete", "invoice"]]),
        ])
        self.assertEqual(source_predictions(part)["overlap_pairs"], set())

    def test_foreign_target_does_not_hide_missing_own_target(self):
        part = fixture_partition([
            raw_story("A", ["delete"], ["invoice"], []),
            raw_story("B", ["delete"], ["invoice"], [["delete", "invoice"]]),
        ])
        sid = next(r["id"] for r in part["records"] if r["text"] == "A")
        self.assertIn((sid, "delete"), source_predictions(part)["dangling_actions"])

    def test_foreign_trigger_does_not_create_cross_persona_evidence(self):
        part = fixture_partition([
            raw_story("A", ["delete"], ["invoice"], [["delete", "invoice"]], "admin", []),
            raw_story("B", ["delete"], ["invoice"], [["delete", "invoice"]], "user", [["user", "delete"]]),
            raw_story("C", ["delete"], ["customer"], [["delete", "customer"]], "admin", [["admin", "delete"]]),
        ])
        self.assertEqual(source_predictions(part)["cross_persona_pairs"], set())

    def test_genuine_same_backlog_overlap_and_cross_persona_are_found(self):
        part = fixture_partition([
            raw_story("A", targets=[["create", "invoice"]], persona="user", triggers=[["user", "create"]]),
            raw_story("B", targets=[["create", "invoice"]], persona="admin", triggers=[["admin", "create"]]),
        ])
        result = source_predictions(part)
        self.assertEqual(len(result["overlap_pairs"]), 1)
        self.assertEqual(len(result["cross_persona_pairs"]), 1)
        self.assertEqual(sum(1 for r in source_snapshot(part)["edges"] if r[0] == "TARGETS"), 2)

    def test_atomicity_boundaries_use_strict_greater_than(self):
        part = fixture_partition([raw_story(str(count), [f"a{i}" for i in range(count)], [], []) for count in range(1, 6)])
        result = source_predictions(part)["predicted"]
        for k in (1, 2, 4):
            expected = {record["id"] for record in part["records"] if int(record["text"]) > k}
            self.assertEqual(result[f"non_atomic_gt{k}"], expected)

    def test_real_appeal_story_cannot_inherit_record_outcome(self):
        result = source_predictions(load_partition("gpt-4-turbo", "g03"))
        group = next(group for group in result["overlap_groups"] if group[:2] == ("record", "outcome"))
        self.assertEqual(set(group[2]), {"g03_02b1af10", "g03_0171156c"})
        self.assertNotIn("g03_19e1d1f9", group[2])

    def test_real_g04_51_fix_remains_dangling(self):
        result = source_predictions(load_partition("gpt-4-turbo", "g04"))
        self.assertIn(("g04_ef4b486c", "fix"), result["dangling_actions"])

    def test_raw_duplicate_alarm_is_projected_to_both_instances(self):
        parts = load_partitions("gpt-4-turbo")
        predictions = {p["pid"]: source_predictions(p) for p in parts}
        report = build_report(parts, predictions, load_ground_truth(), parse_aqusa(load_ground_truth()))
        ids = report["atomicity"]["neo4j_threshold_gt1"]["Predicted_Stories"]
        self.assertIn("G03_45", ids)
        self.assertIn("G03_46", ids)
        means = report["incomplete_means"]
        self.assertFalse(means["metrics_applicable"])
        self.assertNotIn("neo4j", means)
        self.assertEqual(means["historical_annotation_comparison"]["neo4j"]["FP"], 3)
        self.assertFalse(report["missing_benefit"]["aqusa"]["metrics_applicable"])
        self.assertEqual(report["uniqueness"]["etl_invariant"]["identical_supplied_records_coalesced"], 0)


DB_NAME = os.getenv("NEO4J_TEST_DATABASE")
DB_BY_PID = {
    "g03": os.getenv("NEO4J_TEST_DATABASE_G03", DB_NAME),
    "g04": os.getenv("NEO4J_TEST_DATABASE_G04", DB_NAME),
}
DB_ENABLED = bool(all(DB_BY_PID.values()) and os.getenv("NEO4J_PASSWORD"))


@unittest.skipUnless(DB_ENABLED, "Set NEO4J_TEST_DATABASE and NEO4J_PASSWORD for isolated live integration tests")
class TestDatabaseFidelity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if any(name.lower() in {"userstories", "system"} for name in DB_BY_PID.values()):
            raise RuntimeError("Historical/system database is protected")
        from neo4j import GraphDatabase
        cls.driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687"),
            auth=(os.getenv("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
        )
        cls.model = os.getenv("NEO4J_TEST_MODEL", "gpt-4-turbo")
        cls.partitions = load_partitions(cls.model)

    @classmethod
    def tearDownClass(cls):
        cls.driver.close()

    def test_exact_source_nodes_edges_texts_and_query_results(self):
        from graph_database import database_predictions, validate_schema, verify_partition
        for part in self.partitions:
            with self.subTest(pid=part["pid"]):
                with self.driver.session(database=DB_BY_PID[part["pid"]]) as session:
                    validate_schema(session)
                    self.assertEqual(verify_partition(session, part), source_snapshot(part))
                    self.assertEqual(database_predictions(session, part), source_predictions(part))

    def test_composite_identity_constraints(self):
        from graph_queries import CONSTRAINTS
        for database in set(DB_BY_PID.values()):
            with self.subTest(database=database), self.driver.session(database=database) as session:
                rows = session.run("SHOW CONSTRAINTS YIELD labelsOrTypes, properties RETURN labelsOrTypes, properties").data()
                actual = {(tuple(row["labelsOrTypes"]), tuple(row["properties"])) for row in rows}
                for label, fields in CONSTRAINTS.items():
                    expected = tuple(field.strip().split(".")[-1] for field in fields.split(","))
                    self.assertIn(((label,), expected), actual)

    def test_no_backlog_or_model_cross_edges(self):
        for pid, database in DB_BY_PID.items():
            with self.subTest(pid=pid), self.driver.session(database=database) as session:
                row = session.run(
                    "MATCH (n) OPTIONAL MATCH (n)-[r]->() "
                    "RETURN count(CASE WHEN n.pid <> $pid THEN 1 END) AS foreign_nodes, "
                    "count(CASE WHEN r IS NOT NULL AND (startNode(r).pid <> $pid OR endNode(r).pid <> $pid) THEN 1 END) AS foreign_edges",
                    pid=pid,
                ).single()
                self.assertEqual((row["foreign_nodes"], row["foreign_edges"]), (0, 0))


@unittest.skipUnless(DB_ENABLED, "Set NEO4J_TEST_DATABASE and NEO4J_PASSWORD for rolled-back fixture tests")
class TestDatabaseRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_BY_PID["g03"].lower() in {"userstories", "system"}:
            raise RuntimeError("Historical/system database is protected")
        from neo4j import GraphDatabase
        cls.driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687"),
            auth=(os.getenv("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
        )

    @classmethod
    def tearDownClass(cls):
        cls.driver.close()

    def setUp(self):
        self.model = "test-" + uuid.uuid4().hex
        self.session = self.driver.session(database=DB_BY_PID["g03"])
        self.tx = self.session.begin_transaction()

    def tearDown(self):
        self.tx.rollback()
        self.session.close()

    def install(self, records, pid="g03", model=None):
        from graph_database import import_partition
        part = fixture_partition(records, model or self.model, pid)
        self.assertTrue(import_partition(self.tx, part))
        return part

    def check(self, part):
        from graph_database import database_predictions
        result = database_predictions(self.tx, part)
        self.assertEqual(result, source_predictions(part))
        return result

    def test_swapped_pairs_and_missing_own_target(self):
        part = self.install([
            raw_story("A", ["delete", "create"], ["customer", "invoice"], [["delete", "customer"], ["create", "invoice"]]),
            raw_story("B", ["delete"], ["invoice"], [["delete", "invoice"]]),
            raw_story("C", ["delete"], ["invoice"], []),
        ])
        result = self.check(part)
        self.assertEqual(result["overlap_pairs"], set())
        self.assertEqual(len(result["dangling_actions"]), 1)

    def test_foreign_trigger_does_not_create_cross_persona(self):
        part = self.install([
            raw_story("A", ["delete"], ["invoice"], [["delete", "invoice"]], "admin", []),
            raw_story("B", ["delete"], ["invoice"], [["delete", "invoice"]], "user", [["user", "delete"]]),
            raw_story("C", ["delete"], ["customer"], [["delete", "customer"]], "admin", [["admin", "delete"]]),
        ])
        self.assertEqual(self.check(part)["cross_persona_pairs"], set())

    def test_same_names_across_backlogs_and_models_are_disjoint(self):
        one = self.install([raw_story("same", targets=[["create", "invoice"]])])
        two = self.install([raw_story("same", targets=[["create", "invoice"]])], pid="g04")
        three = self.install([raw_story("same", targets=[["create", "invoice"]])], model=self.model + "-other")
        for part in (one, two, three):
            self.assertEqual(self.check(part)["overlap_pairs"], set())
        count = self.tx.run(
            "MATCH (a)-[r]->(b) WHERE a.pid <> b.pid OR a.model <> b.model RETURN count(r) AS n"
        ).single()["n"]
        self.assertEqual(count, 0)

    def test_owned_parallel_edges_and_genuine_cross_persona(self):
        part = self.install([
            raw_story("A", targets=[["create", "invoice"]], persona="user", triggers=[["user", "create"]]),
            raw_story("B", targets=[["create", "invoice"]], persona="admin", triggers=[["admin", "create"]]),
        ])
        result = self.check(part)
        self.assertEqual(len(result["overlap_pairs"]), 1)
        self.assertEqual(len(result["cross_persona_pairs"]), 1)
        count = self.tx.run("MATCH (:Action {model: $model})-[r:TARGETS]->() RETURN count(r) AS n", model=self.model).single()["n"]
        self.assertEqual(count, 2)

    def test_idempotent_import_and_changed_source_rejected(self):
        from graph_database import import_partition, read_snapshot
        part = self.install([raw_story(targets=[["create", "invoice"]])])
        before = read_snapshot(self.tx, self.model, "g03")
        self.assertFalse(import_partition(self.tx, part))
        self.assertEqual(read_snapshot(self.tx, self.model, "g03"), before)
        changed = fixture_partition([raw_story(benefit=None)], self.model)
        with self.assertRaises(ValueError):
            import_partition(self.tx, changed)

    def test_legacy_graph_is_rejected(self):
        from graph_database import validate_schema
        self.tx.run("CREATE (:UserStory {id: $id})", id=self.model).consume()
        with self.assertRaises(ValueError):
            validate_schema(self.tx)

    def test_missing_source_edge_is_detected_by_fidelity_check(self):
        from graph_database import verify_partition
        part = self.install([raw_story(targets=[["create", "invoice"]])])
        # Alter the EXPECTED input, not the database; the mismatch must be detected.
        altered = copy.deepcopy(part)
        altered["records"][0]["targets"].append(["create", "additional"])
        with self.assertRaises(ValueError):
            verify_partition(self.tx, altered)


if __name__ == "__main__":
    unittest.main(verbosity=2)
