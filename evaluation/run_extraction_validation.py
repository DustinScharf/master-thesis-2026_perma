"""Reproduce da Silva's component-extraction evaluation, without LLM/Neo4j calls.

This adapter executes only an explicit set of function definitions from the
reviewed, hash-pinned ``vendor/user-story-extractor/evaluation.py``. The vendor
file is distributed unchanged with attribution. Its imports and executable main block are
not executed. Strict comparison is the default; ``--inclusive`` also runs mode 2.
Relaxed comparison and the problematic BERTScore/main routines are not loaded.

Example, from evaluation/:
    python run_extraction_validation.py

The reference annotates extracted components, not quality defects or redundancy
between stories. Scores measure text-component agreement, not Neo4j import
integrity. The original evaluator scores matched stories only and micro-pools
component TP/FP/FN inside each backlog. Both conventions are retained and reported.
"""

import argparse
import ast
import builtins
import copy
import csv
import hashlib
import json
import math
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
MODELS = ("gpt-4-turbo", "gpt-4o-mini", "ollama3", "chatgpt")
BACKLOGS = ("g03", "g04")
COMPONENTS = ("Persona", "Entity", "Action", "Benefit")
MODE_NAMES = {1: "strict", 2: "inclusive"}
# UTF-8 source with LF line endings; CRLF checkout conversion is harmless.
REVIEWED_SOURCE_SHA256 = "0473e807fdc7941735ae9b36143edd7eee5cc165dbe2271621edb15e8ad2cd8a"
FUNCTIONS = (
    "compare_and_get_results", "sort", "strict_compare", "inclusion_compare",
    "check_inclusion_elements", "count_true_false_positives_negatives",
    "count_total_result_dataset", "total_dataset", "calculate_precision",
    "calculate_recall", "calculate_f_measure", "individual_story",
    "extract_all_baseline_info", "extract_experiment_info",
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read_only_utf8_open(path, mode="r", *args, **kwargs):
    """Make the vendor's implicit text encoding portable, without write access."""
    if mode not in ("r", "rt") or args:
        raise ValueError("The extraction adapter permits UTF-8 text reads only.")
    kwargs.setdefault("encoding", "utf-8")
    return builtins.open(path, mode, **kwargs)


def load_original_functions(source_path):
    """Load reviewed function bodies only; this is not a general Python sandbox."""
    source = Path(source_path).read_bytes().decode("utf-8-sig").replace("\r\n", "\n")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if digest != REVIEWED_SOURCE_SHA256:
        raise ValueError(
            "Unsupported evaluation.py version. Review the external source before "
            "updating REVIEWED_SOURCE_SHA256; no external code was executed."
        )
    parsed = ast.parse(source, filename="external/evaluation.py")
    definitions = {node.name: node for node in parsed.body if isinstance(node, ast.FunctionDef)}
    missing = set(FUNCTIONS).difference(definitions)
    if missing:
        raise ValueError(f"Missing reviewed functions: {sorted(missing)}")
    selected = [definitions[name] for name in FUNCTIONS]
    if any(node.decorator_list or node.args.defaults or node.args.kw_defaults for node in selected):
        raise ValueError("Unexpected executable defaults or decorators in adapter functions.")
    module = ast.Module(body=selected, type_ignores=[])
    namespace = {
        "__builtins__": dict(vars(builtins), open=_read_only_utf8_open),
        "copy": copy, "json": json, "re": re,
    }
    exec(compile(module, "external/evaluation.py", "exec"), namespace)
    return namespace


def read_records(path):
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError(f"Expected a list of story objects in {Path(path).name}.")
    for index, story in enumerate(records, start=1):
        if not isinstance(story, dict) or not isinstance(story.get("Text"), str):
            raise ValueError(f"Invalid story text in {Path(path).name}, row {index}.")
    return records


def matching_text(text):
    """Exactly the vendor's story matching: remove #GNN#, then strip whitespace."""
    return re.sub(r"#G\d{2}#", "", text).strip(" \n\t")


def pair_stories(reference, extracted):
    """Greedy one-to-one matching in file order; retain duplicate occurrences."""
    unused = list(range(len(extracted)))
    pairs = []
    missing = []
    for ref_index, story in enumerate(reference):
        key = matching_text(story["Text"])
        match = next((i for i in unused if matching_text(extracted[i]["Text"]) == key), None)
        if match is None:
            missing.append({"reference_row": ref_index + 1, "text": story["Text"]})
        else:
            unused.remove(match)
            pairs.append([ref_index + 1, match + 1])
    return {
        "reference_stories": len(reference),
        "extracted_stories": len(extracted),
        "matched_stories": len(pairs),
        "reference_coverage": len(pairs) / len(reference) if reference else None,
        "extraction_coverage": len(pairs) / len(extracted) if extracted else None,
        "row_numbering": "one-based [reference row, extraction row]",
        "matched_pairs": pairs,
        "unmatched_reference_stories": missing,
        "unmatched_extracted_stories": [
            {"extraction_row": i + 1, "text": extracted[i]["Text"]} for i in unused
        ],
    }


def evaluate_pair(functions, reference_path, extraction_path, mode, expected_matches):
    if mode not in MODE_NAMES:
        raise ValueError("Only strict (1) and inclusive (2) modes are supported.")
    # The vendor comparison consumes annotation lists; reload for every mode.
    reference, pos_data = functions["extract_all_baseline_info"](reference_path)
    extracted = functions["extract_experiment_info"](extraction_path)
    _, counts, _, _, texts = functions["compare_and_get_results"](
        reference, extracted, mode, pos_data, None
    )
    if len(texts) != expected_matches:
        raise ValueError("Adapter pairing disagrees with the original evaluator.")
    precision, recall, f1 = functions["total_dataset"](counts)
    results = {}
    for index, component in enumerate(COMPONENTS):
        tp, fp, fn = functions["count_total_result_dataset"](counts[index])
        results[component] = {
            "TP": tp, "FP": fp, "FN": fn,
            "precision": precision[index], "recall": recall[index], "f1": f1[index],
        }
    return results


def compare_csv(csv_path, backlog, mode, results):
    """Compare all 12 P/R/F1 values against the supplied historical CSV row."""
    if not csv_path.is_file():
        return {"status": "not_available", "checked_values": 0}
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row["Backlog Name"] == backlog]
    if len(rows) != 1:
        raise ValueError(f"Expected one {backlog} row in {csv_path.name}; found {len(rows)}.")
    row = rows[0]
    if int(row["Comparison Mode"]) != mode:
        raise ValueError(f"Unexpected comparison mode in {csv_path.name}.")
    mismatches = []
    for component in COMPONENTS:
        for key, heading in (("precision", "Precision"), ("recall", "Recall"), ("f1", "F-Measure")):
            expected = float(row[f"{component} {heading}"])
            actual = results[component][key]
            if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12):
                mismatches.append({
                    "component": component, "metric": key,
                    "csv_value": expected, "recomputed_value": actual,
                })
    return {"status": "passed" if not mismatches else "failed", "checked_values": 12,
            "mismatches": mismatches}


def find_extraction(folder, backlog):
    candidates = sorted(folder.glob(f"{backlog}*.json"))
    if len(candidates) != 1:
        raise ValueError(f"Expected exactly one {backlog} JSON in {folder.name}.")
    return candidates[0]


def build_report(extractor_root, inclusive=False):
    root = Path(extractor_root).resolve()
    functions = load_original_functions(root / "evaluation.py")
    inputs = {}

    def record_input(path, scope):
        base = root if scope == "extractor_root" else BASE_DIR
        relative = Path(path).relative_to(base).as_posix()
        key = f"{scope}/{relative}"
        inputs[key] = {"scope": scope, "path": relative, "sha256": sha256(path)}
        return key

    record_input(root / "evaluation.py", "extractor_root")
    record_input(Path(__file__).resolve(), "evaluation")
    report = {
        "schema_version": 1,
        "purpose": "Reproduction of da Silva's text-component extraction evaluation",
        "upstream_dependency": {
            "name": "Thayná Camargo da Silva: user-story-extractor",
            "archive_doi": "10.5281/zenodo.14254059",
            "root_option": "--extractor-root (default: vendor/user-story-extractor, relative to this script)",
            "bundled_subset": "unchanged evaluator, two reference JSON files, three strict-result CSV files containing six evaluated backlog rows; see vendor/user-story-extractor/THIRD_PARTY_NOTICE.md",
            "reviewed_source_sha256_lf_utf8": REVIEWED_SOURCE_SHA256,
            "executed_functions": list(FUNCTIONS),
        },
        "method": {
            "modes": [MODE_NAMES[m] for m in ([1, 2] if inclusive else [1])],
            "score_scale": "ratios in [0, 1], not percentages",
            "matching": "case-sensitive source text; remove #GNN#; strip spaces/newlines/tabs; one-to-one in file order",
            "aggregation": "original micro-aggregation of component TP/FP/FN within each backlog",
            "coverage_policy": "only matched stories contribute to scores, as in the original evaluator; all missing occurrences are reported separately",
            "component_fields": "Persona; Primary + Secondary Entity; Primary + Secondary Action; Benefit",
            "benefit_convention": "the original evaluator compares a one-element Benefit-text list, including an empty string; this is not missing-benefit classification",
            "adapters": "functions-only AST loading of a reviewed hash-pinned source; UTF-8 read-only file opening; explicit occurrence-level coverage",
            "not_evaluated": ["Neo4j import integrity", "semantic relation extraction", "quality defects", "pairwise story redundancy", "BERTScore"],
            "configuration_note": "chatgpt is an artifact-folder identifier; exact model/prompt provenance is not inferred from that name",
        },
        "models": {},
    }
    for model in MODELS:
        report["models"][model] = {}
        for backlog in BACKLOGS:
            reference_path = root / "pos_baseline" / f"{backlog}_baseline_intersecting_pos.json"
            extraction_path = find_extraction(BASE_DIR / "extracted_data" / model, backlog)
            reference = read_records(reference_path)
            extracted = read_records(extraction_path)
            coverage = pair_stories(reference, extracted)
            entry = {
                "reference_input": record_input(reference_path, "extractor_root"),
                "extraction_input": record_input(extraction_path, "evaluation"),
                "coverage": coverage,
                "modes": {},
            }
            # A complete external checkout may additionally verify the local data
            # against its source JSON. The bundled subset deliberately avoids
            # duplicating the eight input files already in extracted_data/.
            archived_folder = root / "extracted-user-stories" / model
            if archived_folder.is_dir():
                original_path = find_extraction(archived_folder, backlog)
                same_records = extracted == read_records(original_path)
                if not same_records:
                    raise ValueError(f"Local {model}/{backlog} data differ from the archived extraction.")
                entry["archived_extraction_input"] = record_input(original_path, "extractor_root")
                entry["local_equals_archived_json"] = same_records
            for mode in ([1, 2] if inclusive else [1]):
                result = evaluate_pair(functions, reference_path, extraction_path, mode, coverage["matched_stories"])
                csv_path = root / "evaluation" / model / f"{MODE_NAMES[mode]}_dataset_results.csv"
                reproduction = compare_csv(csv_path, backlog, mode, result)
                if csv_path.is_file():
                    reproduction["csv_input"] = record_input(csv_path, "extractor_root")
                entry["modes"][MODE_NAMES[mode]] = {"components": result, "csv_reproduction": reproduction}
            report["models"][model][backlog] = entry
    report["inputs"] = [inputs[key] for key in sorted(inputs)]
    checks = [mode["csv_reproduction"] for backlogs in report["models"].values()
              for entry in backlogs.values() for mode in entry["modes"].values()]
    report["reproduction_summary"] = {
        "passed_csv_rows": sum(c["status"] == "passed" for c in checks),
        "failed_csv_rows": sum(c["status"] == "failed" for c in checks),
        "unavailable_csv_rows": sum(c["status"] == "not_available" for c in checks),
        "checked_metric_values": sum(c["checked_values"] for c in checks),
    }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extractor-root", type=Path, default=BASE_DIR / "vendor/user-story-extractor")
    parser.add_argument("--output", type=Path, default=BASE_DIR / "extraction_validation_results.json")
    parser.add_argument("--inclusive", action="store_true", help="Also reproduce the original inclusive mode.")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.extractor_root, args.inclusive)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Extraction validation failed: {error}\n")
    summary = report["reproduction_summary"]
    print(f"Validated 4 configurations x 2 backlogs; {summary['passed_csv_rows']} historical CSV rows reproduced, "
          f"{summary['failed_csv_rows']} mismatches, {summary['unavailable_csv_rows']} CSV rows unavailable.")
    for model, backlogs in report["models"].items():
        for backlog, entry in backlogs.items():
            coverage = entry["coverage"]
            print(f"{model}/{backlog}: {coverage['matched_stories']}/{coverage['reference_stories']} reference stories matched.")
    return 1 if summary["failed_csv_rows"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
