"""Evaluate partitioned graph checks against every raw reference story.

--source-json-only computes the same rules on source relations without claiming a
Neo4j execution. It is useful for an independent import/query regression oracle.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from evaluation_report import build_report, parse_aqusa
from graph_database import database_predictions, validate_schema
from graph_model import BASE_DIR, SCHEMA_VERSION, load_ground_truth, load_partitions, source_predictions
from import_to_neo4j import connect, connection_arguments, database_for_backlog


def main(argv=None):
    parser = connection_arguments(argparse.ArgumentParser(description=__doc__))
    parser.add_argument("--source-json-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if len(args.backlog) != len(set(args.backlog)):
        parser.error("Each backlog may only be selected once")
    partitions = load_partitions(args.model, args.backlog)
    ground_truth = load_ground_truth()
    selected_gt = {pid: ground_truth[pid] for pid in args.backlog}
    aqusa = parse_aqusa(selected_gt)
    if args.source_json_only:
        predictions = {partition["pid"]: source_predictions(partition) for partition in partitions}
    else:
        with connect(args) as driver:
            predictions = {}
            for partition in partitions:
                database = database_for_backlog(args, partition["pid"])
                with driver.session(database=database) as session:
                    validate_schema(session)
                    predictions[partition["pid"]] = database_predictions(session, partition)
    report = build_report(partitions, predictions, selected_gt, aqusa)
    report["protocol"] = {
        "schema_version": SCHEMA_VERSION,
        "execution": "json_reference" if args.source_json_only else "neo4j",
        "database": None if args.source_json_only else {
            pid: database_for_backlog(args, pid) for pid in args.backlog
        },
        "model": args.model,
        "backlogs": args.backlog,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_unit": "raw reference story; canonical graph alarms projected to all same-text reference IDs",
        "inputs": [{key: partition[key] for key in ("model", "pid", "source_file", "source_sha256")} for partition in partitions],
    }
    output = args.output or BASE_DIR / ("evaluation_source_results.json" if args.source_json_only else "evaluation_results.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Evaluation saved: {output}; execution={report['protocol']['execution']}")


if __name__ == "__main__":
    main()
