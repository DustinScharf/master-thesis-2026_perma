"""Database integrity checks shared by import, evaluation and integration tests."""

from graph_model import SCHEMA_VERSION, source_snapshot
from graph_queries import CONSTRAINTS, IMPORT_QUERY, QUERIES, import_parameters


def validate_schema(runner):
    # Constraints must be checked even when the historical graph was emptied.
    constraints = runner.run("SHOW CONSTRAINTS YIELD labelsOrTypes, properties RETURN labelsOrTypes, properties").data()
    if any("UserStory" in row["labelsOrTypes"] and row["properties"] == ["id"] for row in constraints):
        raise ValueError("Legacy UserStory.id-only constraint detected; use a fresh database.")
    # A new database has no label/property tokens yet. Content queries would
    # only emit UnknownLabel/UnknownProperty notifications and cannot find an
    # invalid node or edge when the database contains no nodes at all.
    if runner.run("MATCH (n) RETURN count(n) AS count").single()["count"] == 0:
        return
    invalid_nodes = runner.run("""
        MATCH (n)
        WHERE size(labels(n)) <> 1 OR NOT labels(n)[0] IN $labels
           OR coalesce(n.schema_version, '') <> $version
           OR n.model IS NULL OR n.pid IS NULL
        RETURN count(n) AS count
    """, labels=list(CONSTRAINTS), version=SCHEMA_VERSION).single()["count"]
    if invalid_nodes:
        raise ValueError("Legacy, mixed or foreign graph detected; choose a new empty database. No migration is performed.")
    invalid_edges = runner.run("""
        MATCH (a)-[r]->(b)
        WHERE a.model <> b.model OR a.pid <> b.pid
           OR NOT type(r) IN $types
           OR (type(r) IN ['TARGETS', 'TRIGGERS'] AND r.story_id IS NULL)
           OR (type(r) = 'HAS_STORY' AND NOT (a:Backlog AND b:UserStory))
           OR (type(r) = 'HAS_PERSONA' AND NOT (a:UserStory AND b:Persona))
           OR (type(r) = 'HAS_ACTION' AND NOT (a:UserStory AND b:Action))
           OR (type(r) = 'HAS_ENTITY' AND NOT (a:UserStory AND b:Entity))
           OR (type(r) = 'HAS_BENEFIT' AND NOT (a:UserStory AND b:Benefit))
           OR (type(r) = 'TRIGGERS' AND NOT (a:Persona AND b:Action))
           OR (type(r) = 'TARGETS' AND NOT (a:Action AND b:Entity))
        RETURN count(r) AS count
    """, types=["HAS_STORY", "HAS_PERSONA", "HAS_ACTION", "HAS_ENTITY", "HAS_BENEFIT", "TARGETS", "TRIGGERS"]).single()["count"]
    if invalid_edges:
        raise ValueError("Cross-partition or unowned relationships detected; database rejected.")
    orphan_semantics = runner.run("""
        MATCH (a)-[r:TARGETS|TRIGGERS]->(b)
        WHERE NOT EXISTS {
            MATCH (us:UserStory {model: a.model, pid: a.pid, id: r.story_id})
            MATCH (us)-[]->(a), (us)-[]->(b)
        }
        RETURN count(r) AS count
    """).single()["count"]
    if orphan_semantics:
        raise ValueError("A semantic edge has no valid source story or story membership.")


def initialize_schema(session):
    for label, fields in CONSTRAINTS.items():
        session.run(
            f"CREATE CONSTRAINT qa_v2_{label.lower()} IF NOT EXISTS "
            f"FOR (b:{label}) REQUIRE ({fields}) IS UNIQUE"
        ).consume()


def read_snapshot(runner, model, pid):
    node_rows = runner.run("""
        MATCH (n {model: $model, pid: $pid})
        RETURN labels(n)[0] AS label, coalesce(n.id, n.name, n.pid) AS identity
    """, model=model, pid=pid).data()
    edge_rows = runner.run("""
        MATCH (a {model: $model, pid: $pid})-[r]->(b)
        RETURN type(r) AS type, coalesce(a.id, a.name, a.pid) AS source,
               coalesce(b.id, b.name, b.pid) AS target,
               coalesce(r.story_id, '') AS story_id
    """, model=model, pid=pid).data()
    nodes = {(r["label"], r["identity"]) for r in node_rows}
    edges = {(r["type"], r["source"], r["target"], r["story_id"]) for r in edge_rows}
    if len(nodes) != len(node_rows) or len(edges) != len(edge_rows):
        raise ValueError(f"{model}/{pid}: duplicate stored node or source-relation identity")
    return {"nodes": nodes, "edges": edges}


def verify_partition(runner, partition):
    model, pid = partition["model"], partition["pid"]
    metadata = runner.run("""
        MATCH (b:Backlog {model: $model, pid: $pid})
        RETURN b.source_sha256 AS source_sha256, b.source_record_count AS source_record_count
    """, model=model, pid=pid).single()
    if metadata is None:
        raise ValueError(f"{model}/{pid}: partition not imported")
    if metadata["source_sha256"] != partition["source_sha256"]:
        raise ValueError(f"{model}/{pid}: source fingerprint changed; use a new target database")
    if metadata["source_record_count"] != partition["source_record_count"]:
        raise ValueError(f"{model}/{pid}: incorrect source-record metadata")
    actual, expected = read_snapshot(runner, model, pid), source_snapshot(partition)
    for kind in ("nodes", "edges"):
        if actual[kind] != expected[kind]:
            raise ValueError(
                f"{model}/{pid}: {kind} differ from extraction input: "
                f"{len(expected[kind] - actual[kind])} missing, "
                f"{len(actual[kind] - expected[kind])} additional"
            )
    stored_texts = {
        row["id"]: row["text"] for row in runner.run(
            "MATCH (u:UserStory {model: $model, pid: $pid}) RETURN u.id AS id, u.text AS text",
            model=model, pid=pid,
        )
    }
    if stored_texts != {record["id"]: record["text"] for record in partition["records"]}:
        raise ValueError(f"{model}/{pid}: stored source texts differ from the input")
    return actual


def import_partition(tx, partition):
    existing = tx.run(
        "MATCH (n {model: $model, pid: $pid}) RETURN count(n) AS count",
        model=partition["model"], pid=partition["pid"],
    ).single()["count"]
    if existing:
        verify_partition(tx, partition)
        return False
    tx.run(IMPORT_QUERY, **import_parameters(partition)).consume()
    verify_partition(tx, partition)
    return True


def database_predictions(runner, partition):
    parameters = {"model": partition["model"], "pid": partition["pid"]}
    verify_partition(runner, partition)
    results = {name: runner.run(query, **parameters).data() for name, query in QUERIES.items()}
    predicted = {
        "well_formedness": {r["id"] for r in results["well_formedness"]},
        "missing_benefit": {r["id"] for r in results["missing_benefit"]},
        "incomplete_means": {r["id"] for r in results["dangling_action"]},
    }
    for threshold in (1, 2, 4):
        predicted[f"non_atomic_gt{threshold}"] = {
            row["id"] for row in results["action_counts"] if row["action_count"] > threshold
        }
    return {
        "predicted": predicted,
        "dangling_actions": {(r["id"], r["action"]) for r in results["dangling_action"]},
        "overlap_pairs": {(r["story_1"], r["story_2"], r["action"], r["entity"]) for r in results["overlap_pairs"]},
        "overlap_groups": {(r["action"], r["entity"], tuple(sorted(r["story_ids"]))) for r in results["overlap_candidate"]},
        "cross_persona_pairs": {
            (r["story_1"], r["story_2"], r["persona_1"], r["persona_2"], r["action"], r["entity"])
            for r in results["cross_persona_overlap"]
        },
    }
