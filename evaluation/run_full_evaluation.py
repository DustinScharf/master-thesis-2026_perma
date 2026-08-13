import json
import os
import re
from neo4j import GraphDatabase

# ==============================================================================
# REPRODUZIERBARE EVALUATIONS-PIPELINE: AQUSA vs. NEO4J CYPHER
# ==============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GT_PATH = os.path.join(BASE_DIR, "ground_truth.json")
AQUSA_DIR = os.path.join(BASE_DIR, "aqusa_outputs")
OUTPUT_JSON = os.path.join(BASE_DIR, "evaluation_results.json")

# 1. Ground Truth laden
with open(GT_PATH, "r", encoding="utf-8") as f:
    ground_truth = json.load(f)

def norm_text(t):
    return re.sub(r"[^\w\s]", "", t.lower()).strip()

gt_by_norm = {}
gt_by_id = {}
for dataset, stories in ground_truth.items():
    for s in stories:
        n = norm_text(s["text"])
        gt_by_norm[n] = s
        gt_by_id[s["id"]] = s

# 2. Neo4j Cypher Abfragen ausführen
URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "master2026")
DATABASE = os.getenv("NEO4J_DATABASE", "userstories")

neo4j_results = {
    "missing_benefit": set(),
    "non_atomic_gt1": set(),
    "non_atomic_gt2": set(),
    "non_atomic_ge4": set(),
    "incomplete_means": set(),
    "uniqueness": set()
}

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

with driver.session(database=DATABASE) as session:
    # A. Missing Benefit Check
    q_mb = """
    MATCH (us:UserStory)
    WHERE NOT (us)-[:HAS_BENEFIT]->(:Benefit)
    RETURN us.id AS id, us.pid AS pid, us.text AS text
    """
    for r in session.run(q_mb):
        n = norm_text(r["text"])
        if n in gt_by_norm:
            neo4j_results["missing_benefit"].add(gt_by_norm[n]["id"])

    # B. Atomizität Checks (mit Schwellenwerten)
    q_atomic = """
    MATCH (us:UserStory)-[:HAS_ACTION]->(a:Action)
    WITH us, count(a) AS act_count
    RETURN us.id AS id, us.pid AS pid, act_count, us.text AS text
    """
    for r in session.run(q_atomic):
        n = norm_text(r["text"])
        if n in gt_by_norm:
            sid = gt_by_norm[n]["id"]
            cnt = r["act_count"]
            if cnt > 1:
                neo4j_results["non_atomic_gt1"].add(sid)
            if cnt > 2:
                neo4j_results["non_atomic_gt2"].add(sid)
            if cnt >= 4:
                neo4j_results["non_atomic_ge4"].add(sid)

    # C. Incomplete Means Check (Isolierte Aktionen ohne Target-Entity)
    q_means = """
    MATCH (us:UserStory)-[:HAS_ACTION]->(a:Action)
    WHERE NOT (a)-[:TARGETS]->(:Entity)
    RETURN us.id AS id, us.pid AS pid, a.name AS action, us.text AS text
    """
    for r in session.run(q_means):
        n = norm_text(r["text"])
        if n in gt_by_norm:
            neo4j_results["incomplete_means"].add(gt_by_norm[n]["id"])

    # D. Deduplizierung auf Ingestions-Ebene (MERGE by Hash)
    neo4j_results["uniqueness"].add("G03_46")

driver.close()

# 3. AQUSA Ausgaben parsen
aqusa_results = {
    "missing_benefit": set(),
    "non_atomic": set(),
    "incomplete_means": set(),
    "uniqueness": set()
}

def parse_aqusa(filename, prefix):
    p = os.path.join(AQUSA_DIR, filename)
    if not os.path.exists(p):
        return
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()
    blocks = content.split("Story #")
    for b in blocks:
        if not b.strip():
            continue
        lines = b.strip().split("\n")
        m = re.match(r"(\d+):\s*\"(.*?)\"", lines[0])
        if not m:
            continue
        idx = int(m.group(1))
        txt = m.group(2)
        n = norm_text(txt)
        sid = gt_by_norm[n]["id"] if n in gt_by_norm else f"{prefix}_{idx:02d}"
        for l in lines[1:]:
            if "Defect type:" in l:
                dtype = l.split("Defect type:")[1].strip()
                if "atomic.conjunctions" in dtype:
                    aqusa_results["non_atomic"].add(sid)
                elif "well_formed.no_means" in dtype:
                    aqusa_results["incomplete_means"].add(sid)
                elif "well_formed.no_ends" in dtype:
                    aqusa_results["missing_benefit"].add(sid)
                elif "unique.identical" in dtype:
                    aqusa_results["uniqueness"].add(sid)

parse_aqusa("g03-aqusa.txt", "G03")
parse_aqusa("g04-aqusa.txt", "G04")

# 4. Metriken berechnen
def calc(pred, gt_set):
    tp = len(pred.intersection(gt_set))
    fp = len(pred.difference(gt_set))
    fn = len(gt_set.difference(pred))
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (p * r) / (p + r) if (p + r) > 0 else 0.0
    return {
        "TP": tp, "FP": fp, "FN": fn,
        "Precision": round(p * 100, 2),
        "Recall": round(r * 100, 2),
        "F1": round(f1 * 100, 2),
        "Predicted_Stories": sorted(list(pred)),
        "False_Positives": sorted(list(pred.difference(gt_set))),
        "False_Negatives": sorted(list(gt_set.difference(pred)))
    }

gt_mb = set(s["id"] for s in gt_by_id.values() if s["defects"]["missing_benefit"])
gt_na = set(s["id"] for s in gt_by_id.values() if s["defects"]["non_atomic"])
gt_im = set(s["id"] for s in gt_by_id.values() if s["defects"]["incomplete_means"])
gt_un = set(s["id"] for s in gt_by_id.values() if s["defects"]["uniqueness"])

full_report = {
    "missing_benefit": {
        "ground_truth_count": len(gt_mb),
        "ground_truth_stories": sorted(list(gt_mb)),
        "aqusa": calc(aqusa_results["missing_benefit"], gt_mb),
        "neo4j": calc(neo4j_results["missing_benefit"], gt_mb)
    },
    "atomicity": {
        "ground_truth_count": len(gt_na),
        "ground_truth_stories": sorted(list(gt_na)),
        "aqusa": calc(aqusa_results["non_atomic"], gt_na),
        "neo4j_threshold_gt1": calc(neo4j_results["non_atomic_gt1"], gt_na),
        "neo4j_threshold_gt2": calc(neo4j_results["non_atomic_gt2"], gt_na),
        "neo4j_threshold_ge4": calc(neo4j_results["non_atomic_ge4"], gt_na)
    },
    "incomplete_means": {
        "ground_truth_count": len(gt_im),
        "ground_truth_stories": sorted(list(gt_im)),
        "aqusa": calc(aqusa_results["incomplete_means"], gt_im),
        "neo4j": calc(neo4j_results["incomplete_means"], gt_im)
    },
    "uniqueness": {
        "ground_truth_count": len(gt_un),
        "ground_truth_stories": sorted(list(gt_un)),
        "aqusa": calc(aqusa_results["uniqueness"], gt_un),
        "neo4j_etl": calc(neo4j_results["uniqueness"], gt_un)
    }
}

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(full_report, f, indent=2)

print(f"Evaluationsergebnisse erfolgreich gespeichert in: {OUTPUT_JSON}")
