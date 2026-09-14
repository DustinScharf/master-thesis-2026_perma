"""Shared, case-sensitive source model and reference semantics for the QA artefact.

No LLM calls and no database writes occur in this module. The extraction artefacts
are inputs from da Silva's preceding work, not newly generated annotations.
"""

from collections import defaultdict
from itertools import combinations, product
from pathlib import Path
import hashlib
import json
import re


BASE_DIR = Path(__file__).resolve().parent
SCHEMA_VERSION = "story-provenance-v2"
MODELS = ("gpt-4-turbo", "gpt-4o-mini", "ollama3", "chatgpt")
BACKLOGS = ("g03", "g04")
THRESHOLDS = (1, 2, 4)


def generate_clean_id(pid, text):
    """Keep the historical IDs: the original, unmodified UTF-8 text is hashed."""
    return f"{pid}_{hashlib.md5(text.encode('utf-8')).hexdigest()[:8]}"


def normalize_text(text):
    """Text alignment only; never apply this function to concept names or IDs."""
    without_prefix = re.sub(r"^\s*#G\d{2}#\s*", "", text, flags=re.IGNORECASE)
    return re.sub(r"[^\w\s]", "", without_prefix.lower()).strip()


def _names(value, field):
    if value is None:
        return set()
    if not isinstance(value, list):
        raise ValueError(f"{field}: expected a list of names")
    if any(not isinstance(name, str) or not name.strip() for name in value):
        raise ValueError(f"{field}: names must be non-empty strings")
    return set(value)


def _pairs(value, field):
    if value is None:
        return set()
    if not isinstance(value, list):
        raise ValueError(f"{field}: expected a list of pairs")
    pairs = set()
    for pair in value:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError(f"{field}: each relation must contain exactly two names")
        if any(not isinstance(name, str) or not name.strip() for name in pair):
            raise ValueError(f"{field}: relation endpoints must be non-empty strings")
        pairs.add(tuple(pair))
    return pairs


def prepare_record(raw, model, pid):
    """Unite primary/secondary fields and relation endpoints without renaming.

    Repeated identical relations in one story denote the same extracted fact.
    The same pair in two stories denotes two separately owned graph relations.
    """
    if not isinstance(raw, dict):
        raise ValueError("A story must be a JSON object")
    for field in ("Text", "Persona", "Action", "Entity"):
        if field not in raw:
            raise ValueError(f"Required extraction field missing: {field}")
    text = raw["Text"]
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Text must be a non-empty string")
    personas = _names(raw["Persona"], "Persona")
    concepts = {}
    for kind in ("Action", "Entity"):
        data = raw[kind]
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ValueError(f"{kind}: expected an object")
        concepts[kind] = (
            _names(data.get(f"Primary {kind}"), f"Primary {kind}")
            | _names(data.get(f"Secondary {kind}"), f"Secondary {kind}")
        )
    triggers = _pairs(raw.get("Triggers"), "Triggers")
    targets = _pairs(raw.get("Targets"), "Targets")
    personas.update(persona for persona, _ in triggers)
    concepts["Action"].update(action for _, action in triggers)
    concepts["Action"].update(action for action, _ in targets)
    concepts["Entity"].update(entity for _, entity in targets)
    benefit = raw.get("Benefit")
    if benefit is not None and not isinstance(benefit, str):
        raise ValueError("Benefit must be a string or null")
    return {
        "id": generate_clean_id(pid, text),
        "model": model,
        "pid": pid,
        "text": text,
        "personas": sorted(personas),
        "actions": sorted(concepts["Action"]),
        "entities": sorted(concepts["Entity"]),
        "benefits": [benefit] if benefit and benefit.strip() else [],
        "triggers": [list(pair) for pair in sorted(triggers)],
        "targets": [list(pair) for pair in sorted(targets)],
    }


def prepare_partition(raw_records, model, pid, source_sha256=None):
    if not isinstance(raw_records, list) or not raw_records:
        raise ValueError(f"{model}/{pid}: expected a non-empty list of stories")
    records_by_id = {}
    for raw in raw_records:
        record = prepare_record(raw, model, pid)
        previous = records_by_id.get(record["id"])
        if previous is not None and previous != record:
            raise ValueError(
                f"{model}/{pid}: hash collision or inconsistent extractions "
                f"for the same text ({record['id']})"
            )
        records_by_id[record["id"]] = record
    if source_sha256 is None:
        encoded = json.dumps(raw_records, ensure_ascii=False, sort_keys=True).encode("utf-8")
        source_sha256 = hashlib.sha256(encoded).hexdigest()
    return {
        "model": model,
        "pid": pid,
        "source_sha256": source_sha256,
        "source_record_count": len(raw_records),
        "duplicate_source_records": len(raw_records) - len(records_by_id),
        "records": sorted(records_by_id.values(), key=lambda record: record["id"]),
    }


def load_partition(model, pid, extraction_dir=None):
    directory = Path(extraction_dir or BASE_DIR / "extracted_data") / model
    candidates = sorted(directory.glob(f"{pid}*.json"))
    if len(candidates) != 1:
        raise ValueError(f"{model}/{pid}: expected one input file, found {candidates}")
    path = candidates[0]
    content = path.read_bytes()
    partition = prepare_partition(
        json.loads(content.decode("utf-8-sig")), model, pid,
        hashlib.sha256(content).hexdigest(),
    )
    partition["source_file"] = f"extracted_data/{model}/{path.name}"
    return partition


def load_partitions(model, backlogs=BACKLOGS, extraction_dir=None):
    return [load_partition(model, pid, extraction_dir) for pid in backlogs]


def load_ground_truth(path=None):
    data = json.loads(Path(path or BASE_DIR / "ground_truth.json").read_text(encoding="utf-8"))
    return {pid.lower(): stories for pid, stories in data.items()}


def ground_truth_index(ground_truth):
    index = defaultdict(list)
    seen_ids = set()
    for pid, stories in ground_truth.items():
        for story in stories:
            if story["id"] in seen_ids:
                raise ValueError(f"Duplicate ground-truth ID: {story['id']}")
            seen_ids.add(story["id"])
            index[(pid.lower(), normalize_text(story["text"]))].append(story)
    return dict(index)


def aligned_ids(record, index):
    stories = index.get((record["pid"].lower(), normalize_text(record["text"])))
    if not stories:
        raise ValueError(f"Unmapped extracted story: {record['model']}/{record['id']}")
    return {story["id"] for story in stories}


def expected_defects(ground_truth, category):
    return {
        story["id"] for stories in ground_truth.values() for story in stories
        if story["defects"][category]
    }


def metrics(predicted, expected):
    predicted, expected = set(predicted), set(expected)
    tp, fp, fn = len(predicted & expected), len(predicted - expected), len(expected - predicted)
    f1_denominator = 2 * tp + fp + fn
    return {
        "TP": tp, "FP": fp, "FN": fn,
        "Precision": round(100 * tp / (tp + fp), 2) if tp + fp else None,
        "Recall": round(100 * tp / (tp + fn), 2) if tp + fn else None,
        "F1": round(200 * tp / f1_denominator, 2) if f1_denominator else None,
        "Predicted_Stories": sorted(predicted),
        "False_Positives": sorted(predicted - expected),
        "False_Negatives": sorted(expected - predicted),
    }


def coverage(partitions, ground_truth):
    index = ground_truth_index(ground_truth)
    represented = set()
    duplicate_mappings = []
    for partition in partitions:
        for record in partition["records"]:
            ids = aligned_ids(record, index)
            represented.update(ids)
            if len(ids) > 1:
                duplicate_mappings.append({"graph_story_id": record["id"], "raw_story_ids": sorted(ids)})
    all_ids = {story["id"] for stories in ground_truth.values() for story in stories}
    return {
        "reference_stories": len(all_ids),
        "source_records": sum(p["source_record_count"] for p in partitions),
        "canonical_graph_stories": sum(len(p["records"]) for p in partitions),
        "represented_reference_stories": len(represented),
        "missing_reference_story_ids": sorted(all_ids - represented),
        "shared_text_mappings": duplicate_mappings,
        "rule": "Every graph alarm is projected to all raw stories with the same backlog and normalized text; unrepresented raw stories receive no alarm.",
    }


def source_predictions(partition):
    """Independent set-based reference for the graph rules, not an extraction GT."""
    predicted = {"well_formedness": set(), "missing_benefit": set(), "incomplete_means": set()}
    predicted.update({f"non_atomic_gt{k}": set() for k in THRESHOLDS})
    dangling = set()
    operation_stories = defaultdict(set)
    operation_personas = defaultdict(set)
    for story in partition["records"]:
        sid = story["id"]
        if not all(story[field] for field in ("personas", "actions", "entities")):
            predicted["well_formedness"].add(sid)
        if not story["benefits"]:
            predicted["missing_benefit"].add(sid)
        for k in THRESHOLDS:
            if len(story["actions"]) > k:
                predicted[f"non_atomic_gt{k}"].add(sid)
        targeted_actions = {action for action, _ in story["targets"]}
        for action in set(story["actions"]) - targeted_actions:
            predicted["incomplete_means"].add(sid)
            dangling.add((sid, action))
        for action, entity in story["targets"]:
            operation_stories[(action, entity)].add(sid)
            for persona, triggered_action in story["triggers"]:
                if action == triggered_action:
                    operation_personas[(action, entity)].add((sid, persona))
    overlap = {
        (one, two, action, entity)
        for (action, entity), stories in operation_stories.items()
        for one, two in combinations(sorted(stories), 2)
    }
    cross_persona = {
        (one, two, persona1, persona2, action, entity)
        for (action, entity), stories in operation_personas.items()
        for (one, persona1), (two, persona2) in product(stories, repeat=2)
        if one < two and persona1 != persona2
    }
    return {
        "predicted": predicted,
        "dangling_actions": dangling,
        "overlap_pairs": overlap,
        "overlap_groups": {
            (action, entity, tuple(sorted(stories)))
            for (action, entity), stories in operation_stories.items() if len(stories) > 1
        },
        "cross_persona_pairs": cross_persona,
    }


def source_snapshot(partition):
    """Exact node/edge tuples used by import-fidelity tests."""
    nodes = {("Backlog", partition["pid"])}
    edges = set()
    for story in partition["records"]:
        sid = story["id"]
        nodes.add(("UserStory", sid))
        edges.add(("HAS_STORY", partition["pid"], sid, ""))
        for field, label, relation in (
            ("personas", "Persona", "HAS_PERSONA"),
            ("actions", "Action", "HAS_ACTION"),
            ("entities", "Entity", "HAS_ENTITY"),
            ("benefits", "Benefit", "HAS_BENEFIT"),
        ):
            for name in story[field]:
                nodes.add((label, name))
                edges.add((relation, sid, name, ""))
        for field, relation in (("triggers", "TRIGGERS"), ("targets", "TARGETS")):
            for source, target in story[field]:
                edges.add((relation, source, target, sid))
    return {"nodes": nodes, "edges": edges}


def json_safe(value):
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, set):
        return [json_safe(item) for item in sorted(value)]
    if isinstance(value, (tuple, list)):
        return [json_safe(item) for item in value]
    return value
