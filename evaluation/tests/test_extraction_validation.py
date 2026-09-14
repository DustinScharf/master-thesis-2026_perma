"""Database-independent tests for the explicitly attributed extraction adapter."""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


EVALUATION_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "extraction_validation_adapter", EVALUATION_DIR / "run_extraction_validation.py"
)
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)
EXTRACTOR_ROOT = EVALUATION_DIR / "vendor/user-story-extractor"


class TestExtractionAdapter(unittest.TestCase):
    def test_story_pairing_is_one_to_one_and_preserves_duplicate_occurrences(self):
        coverage = ADAPTER.pair_stories(
            [{"Text": "#G03# same"}, {"Text": "same"}], [{"Text": "same"}]
        )
        self.assertEqual(coverage["matched_pairs"], [[1, 1]])
        self.assertEqual(coverage["reference_coverage"], 0.5)
        self.assertEqual(coverage["unmatched_reference_stories"][0]["reference_row"], 2)

    def test_pairing_keeps_original_case_sensitive_text_convention(self):
        coverage = ADAPTER.pair_stories(
            [{"Text": "#G04# A story\n"}], [{"Text": "a story"}, {"Text": "A story"}]
        )
        self.assertEqual(coverage["matched_pairs"], [[1, 2]])
        self.assertEqual(coverage["unmatched_extracted_stories"][0]["extraction_row"], 1)

    def test_unsupported_source_is_rejected_before_execution(self):
        with patch.object(Path, "read_bytes", return_value=b"raise RuntimeError('must not execute')"):
            with self.assertRaisesRegex(ValueError, "Unsupported evaluation.py"):
                ADAPTER.load_original_functions(Path("not-executed.py"))

    def test_adapter_file_open_rejects_writes(self):
        with self.assertRaises(ValueError):
            ADAPTER._read_only_utf8_open("never-created.txt", "w")

    def test_invalid_comparison_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Only strict"):
            ADAPTER.evaluate_pair({}, None, None, 4, 0)

    @unittest.skipUnless((EXTRACTOR_ROOT / "evaluation.py").is_file(), "Bundled da Silva artifact is not installed")
    def test_original_function_whitelist_and_known_strict_results(self):
        functions = ADAPTER.load_original_functions(EXTRACTOR_ROOT / "evaluation.py")
        self.assertNotIn("bert_score", functions)
        self.assertNotIn("stanza", functions)
        self.assertNotIn("bargraph", functions)
        result = ADAPTER.evaluate_pair(
            functions,
            EXTRACTOR_ROOT / "pos_baseline/g03_baseline_intersecting_pos.json",
            EVALUATION_DIR / "extracted_data/gpt-4-turbo/g03.json",
            1, 55,
        )
        self.assertEqual(result["Action"]["TP"], 125)
        self.assertEqual(result["Action"]["FP"], 11)
        self.assertEqual(result["Action"]["FN"], 20)
        self.assertAlmostEqual(result["Action"]["f1"], 250 / 281)
        check = ADAPTER.compare_csv(
            EXTRACTOR_ROOT / "evaluation/gpt-4-turbo/strict_dataset_results.csv", "g03", 1, result
        )
        self.assertEqual(check["status"], "passed")
        self.assertEqual(check["checked_values"], 12)
        result["Action"]["f1"] = 0.0
        mismatch = ADAPTER.compare_csv(
            EXTRACTOR_ROOT / "evaluation/gpt-4-turbo/strict_dataset_results.csv", "g03", 1, result
        )
        self.assertEqual(mismatch["status"], "failed")
        self.assertEqual(len(mismatch["mismatches"]), 1)

    @unittest.skipUnless((EXTRACTOR_ROOT / "evaluation.py").is_file(), "Bundled da Silva artifact is not installed")
    def test_full_strict_reproduction_and_missing_story_coverage(self):
        report = ADAPTER.build_report(EXTRACTOR_ROOT)
        self.assertEqual(report["reproduction_summary"], {
            "passed_csv_rows": 6, "failed_csv_rows": 0,
            "unavailable_csv_rows": 2, "checked_metric_values": 72,
        })
        coverage = report["models"]["ollama3"]["g04"]["coverage"]
        self.assertEqual(coverage["matched_stories"], 47)
        self.assertEqual(coverage["reference_stories"], 48)
        self.assertEqual(len(coverage["unmatched_reference_stories"]), 1)
        self.assertTrue(all(len(item["sha256"]) == 64 for item in report["inputs"]))
        self.assertTrue(all(not Path(item["path"]).is_absolute() for item in report["inputs"]))


if __name__ == "__main__":
    unittest.main()
