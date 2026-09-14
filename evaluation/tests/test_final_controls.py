"""Regression tests for the supplementary representation and label analyses."""

import copy
import io
import json
from pathlib import Path
import pickle
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graph_model import load_ground_truth
import run_annotation_sensitivity as annotation
import run_representation_audit as representation


class TestAnnotationSensitivity(unittest.TestCase):
    def test_all_positive_labels_have_explained_decisions(self):
        review = annotation.read_review(load_ground_truth())
        rows = review["reviewed_positive_atomicity_labels"]
        self.assertEqual(len(rows), 19)
        self.assertEqual(sum(r["status"] == "ambiguous" for r in rows), 7)
        self.assertFalse(review["incomplete_means"]["classification_metrics_applicable"])

    def test_duplicate_or_missing_review_decision_fails(self):
        ground_truth = load_ground_truth()
        review = annotation.read_review(ground_truth)
        review["reviewed_positive_atomicity_labels"][-1] = copy.deepcopy(review["reviewed_positive_atomicity_labels"][0])
        with patch.object(Path, "read_text", return_value=json.dumps(review)):
            with self.assertRaises(ValueError):
                annotation.read_review(ground_truth)

    def test_symmetric_exclusion_and_known_metrics(self):
        report = annotation.build_report()
        self.assertEqual((report["excluded_scenario_reference_count"], report["excluded_scenario_positive_count"]), (102, 12))
        self.assertEqual(report["results"]["AQUSA"]["without_borderline_cases"]["F1"], 90.91)
        self.assertEqual(report["results"]["gpt-4-turbo:actions>2"]["without_borderline_cases"]["F1"], 31.11)

    def test_all_binary_assignments_are_examined(self):
        report = annotation.build_report()
        self.assertEqual(report["label_assignment_scenarios"], 128)
        for name, result in report["results"].items():
            interval = result["f1_over_all_borderline_assignments"]
            self.assertLessEqual(interval["minimum"], interval["maximum"])
            self.assertEqual(result["scenarios_with_f1_below_aqusa"], 0 if name == "AQUSA" else 128)

    def test_reference_is_not_rewritten(self):
        path = ROOT / "ground_truth.json"
        before = path.read_bytes()
        annotation.build_report()
        self.assertEqual(path.read_bytes(), before)


class TestRepresentationAudit(unittest.TestCase):
    def test_changed_pickle_is_rejected_before_decoding(self):
        with patch.object(Path, "read_bytes", return_value=b"not the verified archive"):
            with self.assertRaises(ValueError):
                representation.load_documents("gpt-4-turbo/g03.pickle")

    def test_external_classes_cannot_be_loaded(self):
        decoder = representation.RestrictedUnpickler(io.BytesIO())
        with self.assertRaises(pickle.UnpicklingError):
            decoder.find_class("os", "system")

    def test_all_206_projections_match_without_metadata(self):
        report = representation.build_report()
        self.assertEqual(report["matched_documents_total"], 206)
        for model in report["projection"].values():
            for row in model.values():
                self.assertEqual(row["nonempty_source_or_semantic_metadata"], 0)

    def test_provenance_counts_include_both_relation_types(self):
        report = representation.build_report()["provenance_sensitivity"]
        self.assertEqual(report["g03"]["false_ownership_by_type"], {"TARGETS": 1, "TRIGGERS": 4})
        self.assertEqual(report["g04"]["false_ownership_by_type"], {"TARGETS": 7, "TRIGGERS": 12})
        self.assertEqual(report["g04"]["without_provenance"], {"dangling_actions": 0, "overlap_groups": 11, "cross_persona_pairs": 7})

    def test_original_types_affect_only_the_reported_main_rules(self):
        report = representation.build_report()["endpoint_type_sensitivity"]["g04"]
        self.assertEqual(len(report["type_deviations"]), 3)
        self.assertEqual(report["original_endpoint_types"], {"dangling_actions": 3, "overlap_groups": 4, "cross_persona_pairs": 1})
        self.assertTrue(report["missing_benefit_and_atomicity_unchanged"])


if __name__ == "__main__":
    unittest.main()
