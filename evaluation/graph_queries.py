"""Single source of the parameterized, provenance-aware Cypher rules."""

from graph_model import SCHEMA_VERSION


CONSTRAINTS = {
    "Backlog": "b.model, b.pid",
    "UserStory": "b.model, b.pid, b.id",
    "Persona": "b.model, b.pid, b.name",
    "Action": "b.model, b.pid, b.name",
    "Entity": "b.model, b.pid, b.name",
    "Benefit": "b.model, b.pid, b.name",
}

IMPORT_QUERY = """
MERGE (backlog:Backlog {model: $model, pid: $pid})
SET backlog.schema_version = $schema_version,
    backlog.source_sha256 = $source_sha256,
    backlog.source_record_count = $source_record_count
WITH backlog
UNWIND $stories AS story
MERGE (us:UserStory {model: $model, pid: $pid, id: story.id})
SET us.text = story.text, us.name = story.text,
    us.schema_version = $schema_version
MERGE (backlog)-[:HAS_STORY]->(us)
FOREACH (name IN story.personas |
    MERGE (p:Persona {model: $model, pid: $pid, name: name})
    SET p.schema_version = $schema_version
    MERGE (us)-[:HAS_PERSONA]->(p)
)
FOREACH (name IN story.actions |
    MERGE (a:Action {model: $model, pid: $pid, name: name})
    SET a.schema_version = $schema_version
    MERGE (us)-[:HAS_ACTION]->(a)
)
FOREACH (name IN story.entities |
    MERGE (e:Entity {model: $model, pid: $pid, name: name})
    SET e.schema_version = $schema_version
    MERGE (us)-[:HAS_ENTITY]->(e)
)
FOREACH (name IN story.benefits |
    MERGE (b:Benefit {model: $model, pid: $pid, name: name})
    SET b.schema_version = $schema_version
    MERGE (us)-[:HAS_BENEFIT]->(b)
)
FOREACH (pair IN story.triggers |
    MERGE (p:Persona {model: $model, pid: $pid, name: pair[0]})
    MERGE (a:Action {model: $model, pid: $pid, name: pair[1]})
    MERGE (p)-[:TRIGGERS {story_id: us.id}]->(a)
)
FOREACH (pair IN story.targets |
    MERGE (a:Action {model: $model, pid: $pid, name: pair[0]})
    MERGE (e:Entity {model: $model, pid: $pid, name: pair[1]})
    MERGE (a)-[:TARGETS {story_id: us.id}]->(e)
)
"""

QUERIES = {
    "well_formedness": """
MATCH (us:UserStory {model: $model, pid: $pid})
WHERE NOT (us)-[:HAS_PERSONA]->(:Persona)
   OR NOT (us)-[:HAS_ACTION]->(:Action)
   OR NOT (us)-[:HAS_ENTITY]->(:Entity)
RETURN us.id AS id, us.pid AS pid, us.text AS text
ORDER BY id
""",
    "missing_benefit": """
MATCH (us:UserStory {model: $model, pid: $pid})
WHERE NOT (us)-[:HAS_BENEFIT]->(:Benefit)
RETURN us.id AS id, us.pid AS pid, us.text AS text
ORDER BY id
""",
    "action_counts": """
MATCH (us:UserStory {model: $model, pid: $pid})
OPTIONAL MATCH (us)-[:HAS_ACTION]->(a:Action)
RETURN us.id AS id, us.pid AS pid, us.text AS text,
       count(DISTINCT a) AS action_count
ORDER BY id
""",
    "fat_story_gt2": """
MATCH (us:UserStory {model: $model, pid: $pid})-[:HAS_ACTION]->(a:Action)
WITH us, count(DISTINCT a) AS action_count
WHERE action_count > 2
RETURN us.id AS id, us.pid AS pid, us.text AS text, action_count
ORDER BY id
""",
    "dangling_action": """
MATCH (us:UserStory {model: $model, pid: $pid})-[:HAS_ACTION]->(a:Action)
WHERE NOT EXISTS {
    MATCH (a)-[target:TARGETS]->(e:Entity)<-[:HAS_ENTITY]-(us)
    WHERE target.story_id = us.id
}
RETURN us.id AS id, us.pid AS pid, us.text AS text, a.name AS action
ORDER BY id, action
""",
    "overlap_candidate": """
MATCH (us:UserStory {model: $model, pid: $pid})-[:HAS_ACTION]->(a:Action)
      -[target:TARGETS]->(e:Entity)<-[:HAS_ENTITY]-(us)
WHERE target.story_id = us.id
WITH a.name AS action, e.name AS entity, us.id AS story_id
ORDER BY story_id
WITH action, entity, collect(DISTINCT story_id) AS story_ids
WHERE size(story_ids) > 1
RETURN action, entity, size(story_ids) AS story_count, story_ids
ORDER BY action, entity
""",
    "overlap_pairs": """
MATCH (u1:UserStory {model: $model, pid: $pid})-[:HAS_ACTION]->(a:Action)
      -[t1:TARGETS]->(e:Entity)<-[:HAS_ENTITY]-(u1),
      (u2:UserStory {model: $model, pid: $pid})-[:HAS_ACTION]->(a)
      -[t2:TARGETS]->(e)<-[:HAS_ENTITY]-(u2)
WHERE u1.id < u2.id AND t1.story_id = u1.id AND t2.story_id = u2.id
RETURN DISTINCT u1.id AS story_1, u2.id AS story_2,
       a.name AS action, e.name AS entity
ORDER BY story_1, story_2, action, entity
""",
    "cross_persona_overlap": """
MATCH (u1:UserStory {model: $model, pid: $pid})-[:HAS_PERSONA]->(p1:Persona)
      -[tr1:TRIGGERS]->(a:Action)-[t1:TARGETS]->(e:Entity),
      (u1)-[:HAS_ACTION]->(a), (u1)-[:HAS_ENTITY]->(e),
      (u2:UserStory {model: $model, pid: $pid})-[:HAS_PERSONA]->(p2:Persona)
      -[tr2:TRIGGERS]->(a)-[t2:TARGETS]->(e),
      (u2)-[:HAS_ACTION]->(a), (u2)-[:HAS_ENTITY]->(e)
WHERE u1.id < u2.id AND p1 <> p2
  AND tr1.story_id = u1.id AND t1.story_id = u1.id
  AND tr2.story_id = u2.id AND t2.story_id = u2.id
RETURN DISTINCT u1.id AS story_1, u2.id AS story_2,
       p1.name AS persona_1, p2.name AS persona_2,
       a.name AS action, e.name AS entity
ORDER BY story_1, story_2, persona_1, persona_2, action, entity
""",
}

BENCHMARK_NAMES = ("missing_benefit", "fat_story_gt2", "dangling_action", "overlap_candidate", "cross_persona_overlap")


def import_parameters(partition):
    return {
        "model": partition["model"], "pid": partition["pid"],
        "schema_version": SCHEMA_VERSION,
        "source_sha256": partition["source_sha256"],
        "source_record_count": partition["source_record_count"],
        "stories": partition["records"],
    }


def standalone_cypher():
    header = (
        "// Provenance-aware QA rules. Read-only; run each query separately.\n"
        "// Set Neo4j Browser parameters: :param model => 'gpt-4-turbo'; :param pid => 'g03'\n"
        "// Repeat with pid='g04'; never compare independent backlogs.\n"
        "// Source of truth: graph_queries.py; checked by the automated tests.\n"
    )
    return header + "".join(f"\n// {name}\n{query.strip()};\n" for name, query in QUERIES.items())
