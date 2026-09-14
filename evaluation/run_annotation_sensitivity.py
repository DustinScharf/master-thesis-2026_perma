"""Reproduce post-hoc atomicity sensitivity without modifying reference labels.

Seven textually motivated borderline cases are excluded symmetrically in one
scenario and assigned all 2**7 binary label combinations in another. These are
conditional sensitivity results, not a new annotation or confidence intervals.
"""

import argparse
import hashlib
import itertools
import json
from pathlib import Path

from evaluation_report import parse_aqusa, projected_predictions
from graph_model import (
    BASE_DIR, MODELS, THRESHOLDS, expected_defects, load_ground_truth,
    load_partitions, metrics, source_predictions,
)


def read_review(ground_truth, path=None):
    path = Path(path or BASE_DIR / "annotation_review.json")
    review = json.loads(path.read_text(encoding="utf-8"))
    rows = review["reviewed_positive_atomicity_labels"]
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != expected_defects(ground_truth, "non_atomic"):
        raise ValueError("Review must cover every positive atomicity label exactly once")
    if any(row["status"] not in {"retained", "ambiguous"} or not row["reason"] for row in rows):
        raise ValueError("Each review decision needs a supported status and explanation")
    return review


def build_report():
    ground_truth = load_ground_truth()
    review = read_review(ground_truth)
    ambiguous = {row["id"] for row in review["reviewed_positive_atomicity_labels"]
                 if row["status"] == "ambiguous"}
    expected = expected_defects(ground_truth, "non_atomic")
    universe = {s["id"] for stories in ground_truth.values() for s in stories}
    alarms = {"AQUSA": parse_aqusa(ground_truth)["non_atomic"]}
    inputs = [BASE_DIR / "ground_truth.json", BASE_DIR / "annotation_review.json",
              BASE_DIR / "aqusa_outputs/g03-aqusa.txt", BASE_DIR / "aqusa_outputs/g04-aqusa.txt"]
    for model in MODELS:
        partitions = load_partitions(model)
        source = {p["pid"]: source_predictions(p) for p in partitions}
        projected = projected_predictions(partitions, source, ground_truth)
        for threshold in THRESHOLDS if model == "gpt-4-turbo" else (2,):
            alarms[f"{model}:actions>{threshold}"] = projected[f"non_atomic_gt{threshold}"]
        inputs.extend(BASE_DIR / p["source_file"] for p in partitions)
    possibilities = []
    borderline_ids = sorted(ambiguous)
    for bits in itertools.product((False, True), repeat=len(borderline_ids)):
        positive = expected - ambiguous | {sid for sid, bit in zip(borderline_ids, bits) if bit}
        possibilities.append({name: metrics(predicted, positive) for name, predicted in alarms.items()})
    return {
        "schema_version": 1,
        "method": review["review_method"],
        "scope": review["scope"],
        "selection_rule": review["selection_rule"],
        "original_reference_count": len(universe),
        "original_positive_count": len(expected),
        "ambiguous_story_ids": borderline_ids,
        "excluded_scenario_reference_count": len(universe - ambiguous),
        "excluded_scenario_positive_count": len(expected - ambiguous),
        "label_assignment_scenarios": len(possibilities),
        "note": "Same exclusion and reference assignments for every tool; fixed alarms. No label file is changed. Ranges are scenario extrema, not statistical confidence intervals.",
        "results": {
            name: {
                "original": metrics(predicted, expected),
                "without_borderline_cases": metrics(predicted - ambiguous, expected - ambiguous),
                "f1_over_all_borderline_assignments": {
                    "minimum": min(row[name]["F1"] for row in possibilities),
                    "maximum": max(row[name]["F1"] for row in possibilities),
                },
                "scenarios_with_f1_below_aqusa": sum(row[name]["F1"] < row["AQUSA"]["F1"] for row in possibilities),
            } for name, predicted in alarms.items()
        },
        "inputs": [{"path": p.relative_to(BASE_DIR).as_posix(),
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in inputs],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BASE_DIR / "annotation_sensitivity_results.json")
    args = parser.parse_args()
    report = build_report()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Annotation sensitivity saved: {args.output}")


if __name__ == "__main__":
    main()
