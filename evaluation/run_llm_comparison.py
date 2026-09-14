"""Compare downstream QA rules on da Silva's saved model extractions.

This is a JSON-based rule evaluation, not a new model run or a measurement of
extraction accuracy. Primary and secondary fields follow the same importer.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from evaluation_report import build_report
from graph_model import (
    BASE_DIR, BACKLOGS, MODELS, SCHEMA_VERSION, load_ground_truth,
    load_partitions, source_predictions, source_snapshot,
)


def model_report(model, ground_truth, backlogs=BACKLOGS):
    partitions = load_partitions(model, backlogs)
    predictions = {partition["pid"]: source_predictions(partition) for partition in partitions}
    report = build_report(partitions, predictions, ground_truth)
    report["fat_story_actions_gt2"] = report["atomicity"]["neo4j_threshold_gt2"]
    report["graph_cardinalities_per_backlog"] = {}
    for partition in partitions:
        snapshot = source_snapshot(partition)
        counts = {
            label: sum(1 for node_label, _ in snapshot["nodes"] if node_label == label)
            for label in ("Backlog", "UserStory", "Persona", "Action", "Entity", "Benefit")
        }
        counts.update({
            relation: sum(1 for edge_type, *_ in snapshot["edges"] if edge_type == relation)
            for relation in ("TRIGGERS", "TARGETS")
        })
        report["graph_cardinalities_per_backlog"][partition["pid"]] = counts
    report["inputs"] = [{key: partition[key] for key in ("model", "pid", "source_file", "source_sha256")} for partition in partitions]
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", choices=MODELS, default=list(MODELS))
    parser.add_argument("--backlog", nargs="+", choices=BACKLOGS, default=list(BACKLOGS))
    parser.add_argument("--output", type=Path, default=BASE_DIR / "llm_comparison_results.json")
    args = parser.parse_args(argv)
    if len(set(args.models)) != len(args.models) or len(set(args.backlog)) != len(args.backlog):
        parser.error("Repeated model/backlog arguments are not allowed")
    ground_truth = load_ground_truth()
    report = {
        "protocol": {
            "schema_version": SCHEMA_VERSION,
            "execution": "json_reference",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "models": args.models,
            "backlogs": args.backlog,
            "note": "Downstream QA on saved extractions; not Neo4j runtime, new LLM inference, or extraction-ground-truth accuracy. No model is selected automatically on these test outcomes.",
        },
        "models": {model: model_report(model, ground_truth, args.backlog) for model in args.models},
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"JSON-reference model comparison saved: {args.output}")


if __name__ == "__main__":
    main()
