"""Read-only checks of archived Pickle/JSON projections and representation effects.

No Neo4j import or LLM call is performed. Pickles are accepted only with the
four pinned archive hashes and are decoded into inert records; original classes
and their code are never imported. The identity-collapse experiment operates on
the documented JSON target schema, not a live LangChain import.
"""

import argparse
from collections import Counter
import copy
import hashlib
import io
import json
from pathlib import Path
import pickle

from graph_model import (
    BASE_DIR, BACKLOGS, aligned_ids, ground_truth_index, load_ground_truth,
    load_partition, source_predictions,
)


ARCHIVE = BASE_DIR / "vendor/user-story-extractor"
PICKLE_HASHES = {
    "gpt-4-turbo/g03.pickle": "229a38999820d13d6977874941dc39b8ddaeeb9827d1b60a64e16a253b39a189",
    "gpt-4-turbo/g04.pickle": "21d281f879268778a1e5a4c0f161d57a074bc1637c563ead525617b7a2bfbab1",
    "gpt-4o-mini/g03.pickle": "57f59e5d38055b02e970f15b29d7539d28aa5a5396d9ef334a5227fd661132bb",
    "gpt-4o-mini/g04.pickle": "cfeceee8640bf710fabe3e5cb7d9d2784028c357f34781783dea482addeeaffb",
}


class InertRecord:
    def __setstate__(self, state):
        self.__dict__.update(state.get("__dict__", state))


class RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        graph_class = module == "langchain_community.graphs.graph_document" and name in {
            "GraphDocument", "Node", "Relationship",
        }
        document_class = (module, name) == ("langchain_core.documents.base", "Document")
        if graph_class or document_class:
            return InertRecord
        raise pickle.UnpicklingError(f"Unsupported archive class: {module}.{name}")


def load_documents(key):
    data = (ARCHIVE / "pickle" / key).read_bytes()
    if hashlib.sha256(data).hexdigest() != PICKLE_HASHES[key]:
        raise ValueError("Pickle differs from the verified version-1 archive")
    return RestrictedUnpickler(io.BytesIO(data)).load()


def check_projection(documents, raw_records):
    by_text = {r["Text"]: r for r in raw_records}
    if len(by_text) != len(raw_records) or len(documents) != len(raw_records):
        raise ValueError("Projection check requires one-to-one story texts")
    matched = set()
    nonempty_metadata = 0
    for document in documents:
        text = document.source.page_content
        if text not in by_text or text in matched:
            raise ValueError("Unmatched or repeated Pickle source text")
        matched.add(text)
        raw = by_text[text]
        expected = {
            "Persona": raw["Persona"],
            "Action": raw["Action"]["Primary Action"] + raw["Action"]["Secondary Action"],
            "Entity": raw["Entity"]["Primary Entity"] + raw["Entity"]["Secondary Entity"],
            "Benefit": [raw["Benefit"]] if raw.get("Benefit") else [],
        }
        for kind, values in expected.items():
            if Counter(n.id for n in document.nodes if n.type == kind) != Counter(values):
                raise ValueError(f"Component projection differs: {kind}")
        for kind, field in (("TRIGGERS", "Triggers"), ("TARGETS", "Targets")):
            actual = Counter((r.source.id, r.target.id) for r in document.relationships if r.type == kind)
            if actual != Counter(tuple(pair) for pair in raw[field]):
                raise ValueError(f"Relation-name projection differs: {kind}")
        nonempty_metadata += bool(document.source.metadata)
        nonempty_metadata += sum(bool(r.properties) for r in document.relationships
                                 if r.type in {"TRIGGERS", "TARGETS"})
    return {"matched_documents": len(matched), "nonempty_source_or_semantic_metadata": nonempty_metadata}


def summary(partition):
    result = source_predictions(partition)
    return {key: len(result[key]) for key in ("dangling_actions", "overlap_groups", "cross_persona_pairs")}


def collapse_provenance(partition, reference_index):
    changed = copy.deepcopy(partition)
    all_pairs = {field: {tuple(pair) for r in partition["records"] for pair in r[field]}
                 for field in ("targets", "triggers")}
    false_ownership = []
    for record in changed["records"]:
        for field, pairs in all_pairs.items():
            left = record["actions" if field == "targets" else "personas"]
            right = record["entities" if field == "targets" else "actions"]
            original = {tuple(pair) for pair in record[field]}
            inferred = {(a, b) for a, b in pairs if a in left and b in right}
            for pair in sorted(inferred - original):
                false_ownership.append({"story_id": record["id"],
                                        "raw_story_ids": sorted(aligned_ids(record, reference_index)),
                                        "relation": field.upper(), "pair": list(pair)})
            record[field] = sorted(inferred)
    occurrences = sum(len(r[field]) for r in partition["records"] for field in all_pairs)
    return {
        "scope": "Collapse type-and-endpoint-identical relations in the JSON target schema; infer ownership from endpoint membership. No live import.",
        "merged_semantic_occurrences": occurrences - sum(len(pairs) for pairs in all_pairs.values()),
        "false_ownership_count": len(false_ownership),
        "false_ownership_by_type": {t: sum(r["relation"] == t for r in false_ownership)
                                    for t in ("TARGETS", "TRIGGERS")},
        "false_ownership": false_ownership,
        "with_provenance": summary(partition),
        "without_provenance": summary(changed),
    }


def strict_endpoint_types(partition, documents, reference_index):
    changed = copy.deepcopy(partition)
    by_text = {d.source.page_content: d for d in documents}
    differences = []
    for record in changed["records"]:
        document = by_text[record["text"]]
        # Use original types for all concept nodes and relationship endpoints.
        nodes = list(document.nodes)
        for edge in document.relationships:
            nodes.extend((edge.source, edge.target))
        for kind, field in (("Persona", "personas"), ("Action", "actions"), ("Entity", "entities")):
            record[field] = sorted({n.id for n in nodes if n.type == kind})
        for kind, field, source_type, target_type in (
            ("TARGETS", "targets", "Action", "Entity"),
            ("TRIGGERS", "triggers", "Persona", "Action"),
        ):
            record[field] = []
            for edge in document.relationships:
                if edge.type != kind:
                    continue
                if (edge.source.type, edge.target.type) == (source_type, target_type):
                    record[field].append((edge.source.id, edge.target.id))
                else:
                    differences.append({"story_id": record["id"],
                                        "raw_story_ids": sorted(aligned_ids(record, reference_index)),
                                        "relation": kind, "source": [edge.source.id, edge.source.type],
                                        "target": [edge.target.id, edge.target.type]})
            record[field] = sorted(set(record[field]))
    original_rules = source_predictions(partition)["predicted"]
    strict_rules = source_predictions(changed)["predicted"]
    return {
        "scope": "Keep original endpoint types; apply the same typed Action-to-Entity and Persona-to-Action rules. This is a source-level sensitivity calculation, not a second Neo4j import.",
        "type_deviations": differences,
        "json_target_schema": summary(partition),
        "original_endpoint_types": summary(changed),
        "missing_benefit_and_atomicity_unchanged": all(
            original_rules[k] == strict_rules[k] for k in original_rules
            if k == "missing_benefit" or k.startswith("non_atomic")
        ),
    }


def build_report():
    index = ground_truth_index(load_ground_truth())
    report = {"schema_version": 1, "archive_doi": "10.5281/zenodo.14254059",
              "execution": "offline_source_checks", "projection": {},
              "provenance_sensitivity": {}, "endpoint_type_sensitivity": {}, "inputs": []}
    for model in ("gpt-4-turbo", "gpt-4o-mini"):
        report["projection"][model] = {}
        for pid in BACKLOGS:
            key = f"{model}/{pid}.pickle"
            documents = load_documents(key)
            source_path = BASE_DIR / "extracted_data" / model / f"{pid}.json"
            raw = json.loads(source_path.read_text(encoding="utf-8"))
            report["projection"][model][pid] = check_projection(documents, raw)
            for path in (ARCHIVE / "pickle" / key, source_path):
                report["inputs"].append({"path": path.relative_to(BASE_DIR).as_posix(),
                                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            if model == "gpt-4-turbo":
                partition = load_partition(model, pid)
                report["provenance_sensitivity"][pid] = collapse_provenance(partition, index)
                report["endpoint_type_sensitivity"][pid] = strict_endpoint_types(partition, documents, index)
    report["matched_documents_total"] = sum(r["matched_documents"] for model in report["projection"].values() for r in model.values())
    path = BASE_DIR / "ground_truth.json"
    report["inputs"].append({"path": "ground_truth.json", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BASE_DIR / "representation_audit_results.json")
    args = parser.parse_args()
    report = build_report()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Representation audit saved: {args.output}")


if __name__ == "__main__":
    main()
