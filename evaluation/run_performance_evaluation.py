"""Per-backlog warm-cache microbenchmark of the shared Cypher QA rules."""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import statistics
import sys
import time

import neo4j

from graph_database import validate_schema, verify_partition
from graph_model import BASE_DIR, SCHEMA_VERSION, load_partitions
from graph_queries import BENCHMARK_NAMES, QUERIES
from import_to_neo4j import connect, connection_arguments, database_for_backlog


def percentile(values, fraction):
    if not values or not 0 < fraction <= 1:
        raise ValueError("Expected non-empty observations and 0 < fraction <= 1")
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def sum_db_hits(plan):
    if not plan:
        return 0
    own_hits = int(plan.get("args", {}).get("DbHits", 0) or 0)
    return own_hits + sum(sum_db_hits(child) for child in plan.get("children", []))


def benchmark_query(session, query, parameters, warmups, runs):
    for _ in range(warmups):
        list(session.run(query, **parameters))
    elapsed_ms = []
    result_rows = None
    for _ in range(runs):
        start = time.perf_counter_ns()
        rows = list(session.run(query, **parameters))
        elapsed_ms.append((time.perf_counter_ns() - start) / 1_000_000)
        if result_rows is not None and result_rows != len(rows):
            raise RuntimeError("The result population changed during the benchmark")
        result_rows = len(rows)
    profiled = session.run("PROFILE " + query, **parameters)
    list(profiled)
    summary = profiled.consume()
    return {
        "result_rows": result_rows,
        "db_hits": sum_db_hits(summary.profile),
        "median_ms": round(statistics.median(elapsed_ms), 3),
        "p95_ms": round(percentile(elapsed_ms, 0.95), 3),
        "minimum_ms": round(min(elapsed_ms), 3),
        "maximum_ms": round(max(elapsed_ms), 3),
    }


def main(argv=None):
    parser = connection_arguments(argparse.ArgumentParser(description=__doc__))
    parser.add_argument("--warmups", type=int, default=25)
    parser.add_argument("--runs", type=int, default=250)
    parser.add_argument("--output", type=Path, default=BASE_DIR / "performance_results.json")
    args = parser.parse_args(argv)
    if args.warmups < 0 or args.runs < 1:
        parser.error("Warmups must be non-negative and measured runs positive")
    if len(set(args.backlog)) != len(args.backlog):
        parser.error("Repeated backlog arguments are not allowed")
    partitions = load_partitions(args.model, args.backlog)
    with connect(args) as driver:
        measurements = {}
        components = None
        for partition in partitions:
            database = database_for_backlog(args, partition["pid"])
            with driver.session(database=database) as session:
                validate_schema(session)
                verify_partition(session, partition)
                if components is None:
                    components = session.run(
                        "CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition"
                    ).data()
                params = {"model": partition["model"], "pid": partition["pid"]}
                measurements[partition["pid"]] = {
                    name: benchmark_query(session, QUERIES[name], params, args.warmups, args.runs)
                    for name in BENCHMARK_NAMES
                }
    report = {
        "protocol": {
            "schema_version": SCHEMA_VERSION,
            "execution": "neo4j",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "database": {pid: database_for_backlog(args, pid) for pid in args.backlog},
            "model": args.model,
            "backlogs": args.backlog,
            "user_story_nodes_per_backlog": {p["pid"]: len(p["records"]) for p in partitions},
            "warmup_runs_per_query": args.warmups,
            "measured_runs_per_query": args.runs,
            "timing": "client wall time including driver round trip",
            "execution_conditions": (
                "each backlog in its own physical database; sequential; warm cache; complete result consumption"
                if args.separate_databases
                else "each disjoint backlog measured separately in one selected database; sequential; warm cache; complete result consumption"
            ),
            "inputs": [{key: p[key] for key in ("model", "pid", "source_file", "source_sha256")} for p in partitions],
        },
        "environment": {
            "python": sys.version.split()[0],
            "neo4j_driver": neo4j.__version__,
            "platform": platform.platform(),
            "database_components": components,
        },
        "measurements_per_backlog": measurements,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Per-backlog benchmark saved: {args.output}")


if __name__ == "__main__":
    main()
