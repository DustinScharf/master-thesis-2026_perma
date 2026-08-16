"""Reproduzierbarer Warm-Cache-Kleinbenchmark der zentralen Cypher-Regeln."""

import json
import math
import os
import platform
import statistics
import sys
import time

import neo4j
from neo4j import GraphDatabase


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_JSON = os.path.join(BASE_DIR, "performance_results.json")

URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD")
DATABASE = os.getenv("NEO4J_DATABASE", "userstories")

WARMUP_RUNS = 25
MEASURED_RUNS = 250

QUERIES = {
    "missing_benefit": """
        MATCH (us:UserStory)
        WHERE NOT (us)-[:HAS_BENEFIT]->(:Benefit)
        RETURN us.id AS Story_ID, us.pid AS Project, us.text AS Text
    """,
    "fat_story_gt2": """
        MATCH (us:UserStory)-[:HAS_ACTION]->(a:Action)
        WITH us, count(DISTINCT a) AS action_count,
             collect(DISTINCT a.name) AS actions
        WHERE action_count > 2
        RETURN us.id AS Story_ID, us.pid AS Project, action_count, actions,
               us.text AS Text
        ORDER BY action_count DESC
    """,
    "dangling_action": """
        MATCH (us:UserStory)-[:HAS_ACTION]->(a:Action)
        WHERE NOT ((a)-[:TARGETS]->(:Entity)<-[:HAS_ENTITY]-(us))
        RETURN us.id AS Story_ID, us.pid AS Project, a.name AS Action,
               us.text AS Text
    """,
    "overlap_candidate": """
        MATCH (us:UserStory)-[:HAS_ACTION]->(a:Action)
              -[:TARGETS]->(e:Entity)<-[:HAS_ENTITY]-(us)
        WITH a.name AS Action, e.name AS Entity,
             collect(DISTINCT us) AS stories,
             count(DISTINCT us) AS story_count
        WHERE story_count > 1
        RETURN Action, Entity, story_count,
               [s IN stories | s.id] AS Story_IDs
        ORDER BY story_count DESC
    """,
    "cross_persona_overlap": """
        MATCH (us1:UserStory)-[:HAS_PERSONA]->(p1:Persona)
              -[:TRIGGERS]->(a:Action)-[:TARGETS]->(e:Entity),
              (us1)-[:HAS_ACTION]->(a), (us1)-[:HAS_ENTITY]->(e),
              (us2:UserStory)-[:HAS_PERSONA]->(p2:Persona)-[:TRIGGERS]->(a),
              (us2)-[:HAS_ACTION]->(a), (us2)-[:HAS_ENTITY]->(e)
        WHERE us1.id < us2.id AND p1 <> p2
        RETURN DISTINCT us1.id AS Story_1, us2.id AS Story_2,
               p1.name AS Persona_1, p2.name AS Persona_2,
               a.name AS Shared_Action, e.name AS Shared_Entity
    """,
}


def percentile(values, fraction):
    """Nearest-rank percentile for a non-empty sequence."""
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def sum_db_hits(plan):
    """Sum the per-operator DB Hits from a Neo4j PROFILE plan."""
    if not plan:
        return 0
    own_hits = int(plan.get("args", {}).get("DbHits", 0) or 0)
    return own_hits + sum(sum_db_hits(child) for child in plan.get("children", []))


def benchmark_query(session, query):
    for _ in range(WARMUP_RUNS):
        list(session.run(query))

    elapsed_ms = []
    result_rows = 0
    for _ in range(MEASURED_RUNS):
        start = time.perf_counter_ns()
        rows = list(session.run(query))
        elapsed_ms.append((time.perf_counter_ns() - start) / 1_000_000)
        result_rows = len(rows)

    profiled = session.run("PROFILE " + query)
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


def main():
    if not PASSWORD:
        raise RuntimeError("NEO4J_PASSWORD muss als Umgebungsvariable gesetzt sein.")
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session(database=DATABASE) as session:
        components = session.run(
            "CALL dbms.components() YIELD name, versions, edition "
            "RETURN name, versions, edition"
        ).data()
        story_count = session.run(
            "MATCH (us:UserStory) RETURN count(us) AS count"
        ).single()["count"]
        measurements = {
            name: benchmark_query(session, query)
            for name, query in QUERIES.items()
        }
    driver.close()

    report = {
        "protocol": {
            "database": DATABASE,
            "user_story_nodes": story_count,
            "warmup_runs_per_query": WARMUP_RUNS,
            "measured_runs_per_query": MEASURED_RUNS,
            "timing": "client wall time including the local driver round trip",
            "execution": "sequential, warm cache, complete result consumption",
        },
        "environment": {
            "python": sys.version.split()[0],
            "neo4j_driver": neo4j.__version__,
            "platform": platform.platform(),
            "database_components": components,
        },
        "measurements": measurements,
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as output:
        json.dump(report, output, indent=2, ensure_ascii=False)
    print(f"Performance-Ergebnisse gespeichert in: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
