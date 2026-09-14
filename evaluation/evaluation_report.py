"""Raw-story evaluation, separate coverage accounting, and unsupported baselines."""

from collections import defaultdict
from pathlib import Path
import re

from graph_model import (
    BASE_DIR, THRESHOLDS, aligned_ids, coverage, expected_defects,
    ground_truth_index, json_safe, metrics, normalize_text,
)


def parse_aqusa(ground_truth, directory=None):
    result = {"non_atomic": set(), "incomplete_means": set(), "uniqueness": set()}
    defect_types = {
        "atomic.conjunctions": "non_atomic",
        "well_formed.no_means": "incomplete_means",
        "unique.identical": "uniqueness",
    }
    for pid, stories in ground_truth.items():
        path = Path(directory or BASE_DIR / "aqusa_outputs") / f"{pid}-aqusa.txt"
        if not path.is_file():
            raise ValueError(f"AQUSA output missing: {path.name}")
        by_id = {story["id"]: story for story in stories}
        content = path.read_text(encoding="utf-8")
        blocks = content.split("Story #")
        if content.strip() and len(blocks) == 1:
            raise ValueError(f"Unrecognized AQUSA output: {path.name}")
        for block in blocks[1:]:
            lines = block.strip().splitlines()
            match = re.fullmatch(r'(\d+):\s*"(.*)"', lines[0])
            if not match:
                raise ValueError(f"Malformed AQUSA story header in {path.name}")
            sid = f"{pid.upper()}_{int(match.group(1)):02d}"
            if sid not in by_id or normalize_text(match.group(2)) != normalize_text(by_id[sid]["text"]):
                raise ValueError(f"AQUSA story number/text mismatch: {sid}")
            for line in lines[1:]:
                if "Defect type:" in line:
                    defect_type = line.split("Defect type:", 1)[1].strip()
                    if defect_type in defect_types:
                        result[defect_types[defect_type]].add(sid)
    return result


def projected_predictions(partitions, predictions_by_pid, ground_truth):
    index = ground_truth_index(ground_truth)
    projected = defaultdict(set)
    for partition in partitions:
        mapping = {record["id"]: aligned_ids(record, index) for record in partition["records"]}
        for rule, ids in predictions_by_pid[partition["pid"]]["predicted"].items():
            for sid in ids:
                if sid not in mapping:
                    raise ValueError(f"Unknown predicted graph-story ID: {sid}")
                projected[rule].update(mapping[sid])
    return projected


def etl_invariant(partitions, ground_truth):
    raw_duplicate_groups = []
    for pid, stories in ground_truth.items():
        by_text = defaultdict(list)
        for story in stories:
            by_text[story["text"]].append(story["id"])
        raw_duplicate_groups.extend(
            {"pid": pid, "story_ids": ids} for ids in by_text.values() if len(ids) > 1
        )
    return {
        "classification_output": False,
        "metrics_applicable": False,
        "raw_exact_duplicate_groups": raw_duplicate_groups,
        "supplied_source_records": sum(partition["source_record_count"] for partition in partitions),
        "canonical_import_records": sum(len(partition["records"]) for partition in partitions),
        "identical_supplied_records_coalesced": sum(partition["duplicate_source_records"] for partition in partitions),
        "note": "The supplied extraction subset is inspected separately from raw-text duplicates. No duplicate detection or coalescing is attributed to this import unless repeated records actually occur in its input. Graph fidelity is a structural invariant, not a defect-classification metric.",
    }


def build_report(partitions, predictions_by_pid, ground_truth, aqusa=None, include_partitions=True):
    selected_gt = {partition["pid"]: ground_truth[partition["pid"]] for partition in partitions}
    predictions = projected_predictions(partitions, predictions_by_pid, selected_gt)
    report = {"coverage": coverage(partitions, selected_gt)}
    for category in ("missing_benefit", "incomplete_means"):
        expected = expected_defects(selected_gt, category)
        report[category] = {
            "ground_truth_count": len(expected),
            "ground_truth_stories": sorted(expected),
            "neo4j": metrics(predictions[category], expected),
        }
    expected = expected_defects(selected_gt, "non_atomic")
    report["atomicity"] = {
        "ground_truth_count": len(expected), "ground_truth_stories": sorted(expected),
        **{f"neo4j_threshold_gt{k}": metrics(predictions[f"non_atomic_gt{k}"], expected) for k in THRESHOLDS},
    }
    report["well_formedness"] = {
        "metrics_applicable": False,
        "projected_alarms": sorted(predictions["well_formedness"]),
        "note": "Structural graph rule; no separate well-formedness labels in the supplied defect ground truth.",
    }
    expected_unique = expected_defects(selected_gt, "uniqueness")
    report["uniqueness"] = {
        "ground_truth_count": len(expected_unique),
        "ground_truth_stories": sorted(expected_unique),
        "etl_invariant": etl_invariant(partitions, selected_gt),
    }
    if aqusa is not None:
        selected_ids = {story["id"] for stories in selected_gt.values() for story in stories}
        report["missing_benefit"]["aqusa"] = {
            "implemented": False, "metrics_applicable": False, "status": "not_implemented",
            "note": "AQUSA v1 has no dedicated missing-benefit check; no performance comparison is reported.",
        }
        for report_name, category in (("atomicity", "non_atomic"), ("incomplete_means", "incomplete_means"), ("uniqueness", "uniqueness")):
            report[report_name]["aqusa"] = metrics(aqusa[category] & selected_ids, expected_defects(selected_gt, category))
    # Preserve the historical arithmetic, but do not expose it as a validated
    # classifier score when the only positive reference label is disputed.
    means = report["incomplete_means"]
    means["metrics_applicable"] = False
    means["status"] = "qualitative_only_unconfirmed_positive_reference"
    means["projected_alarms"] = sorted(predictions["incomplete_means"])
    means["historical_annotation_comparison"] = {
        tool: means.pop(tool) for tool in ("neo4j", "aqusa") if tool in means
    }
    means["note"] = (
        "The original label G03_54 is retained, not independently confirmed. "
        "Historical counts are supplied only for traceability; no regular "
        "precision/recall/F1 comparison is claimed for this category."
    )
    report["exploratory"] = {
        "metrics_applicable": False,
        "note": "Source-confirmed shared relation patterns are review candidates, not confirmed semantic redundancies or conflicts. No pairwise redundancy ground truth is available here.",
        "per_backlog": {
            partition["pid"]: {
                name: json_safe(predictions_by_pid[partition["pid"]][name])
                for name in ("dangling_actions", "overlap_groups", "overlap_pairs", "cross_persona_pairs")
            }
            for partition in partitions
        },
    }
    if include_partitions:
        report["per_backlog"] = {
            partition["pid"]: build_report([partition], predictions_by_pid, selected_gt, aqusa, False)
            for partition in partitions
        }
    return report
