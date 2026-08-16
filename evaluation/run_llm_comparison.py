"""Reproduzierbarer FF4-Vergleich direkt auf den JSON-Extraktionsartefakten."""

import json
import os
import re


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXTRACTION_DIR = os.path.join(BASE_DIR, "extracted_data")
GROUND_TRUTH_PATH = os.path.join(BASE_DIR, "ground_truth.json")
OUTPUT_PATH = os.path.join(BASE_DIR, "llm_comparison_results.json")
MODELS = ("gpt-4-turbo", "gpt-4o-mini", "ollama3", "chatgpt")
DATASETS = ("g03", "g04")


def normalize_text(text):
    """Normalisiert Text und entfernt optionale #G03#-/#G04#-Präfixe."""
    without_prefix = re.sub(r"^\s*#G\d{2}#\s*", "", text, flags=re.IGNORECASE)
    return re.sub(r"[^\w\s]", "", without_prefix.lower()).strip()


def load_model_records(model):
    records = []
    model_dir = os.path.join(EXTRACTION_DIR, model)
    for dataset in DATASETS:
        candidates = sorted(
            name
            for name in os.listdir(model_dir)
            if name.startswith(dataset) and name.endswith(".json")
        )
        if len(candidates) != 1:
            raise RuntimeError(
                f"Erwartete genau eine JSON-Datei für {model}/{dataset}, "
                f"gefunden: {candidates}"
            )
        path = os.path.join(model_dir, candidates[0])
        with open(path, "r", encoding="utf-8") as handle:
            records.extend(json.load(handle))
    return records


def metrics(predicted, expected):
    tp = len(predicted & expected)
    fp = len(predicted - expected)
    fn = len(expected - predicted)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "Precision": round(precision * 100, 2),
        "Recall": round(recall * 100, 2),
        "F1": round(f1 * 100, 2),
        "Predicted_Stories": sorted(predicted),
        "False_Positives": sorted(predicted - expected),
        "False_Negatives": sorted(expected - predicted),
    }


def main():
    with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as handle:
        ground_truth = json.load(handle)

    gt_stories = [story for stories in ground_truth.values() for story in stories]
    gt_by_text = {normalize_text(story["text"]): story for story in gt_stories}
    expected_missing_benefit = {
        story["id"] for story in gt_stories if story["defects"]["missing_benefit"]
    }
    expected_non_atomic = {
        story["id"] for story in gt_stories if story["defects"]["non_atomic"]
    }

    report = {}
    for model in MODELS:
        records = load_model_records(model)
        primary_personas = set()
        primary_actions = set()
        primary_entities = set()
        benefits = set()
        missing_benefit = set()
        non_atomic_gt2 = set()
        unmapped = []

        for record in records:
            primary_personas.update(record.get("Persona") or [])
            action_data = record.get("Action") or {}
            entity_data = record.get("Entity") or {}
            record_primary_actions = set(action_data.get("Primary Action") or [])
            record_primary_entities = set(entity_data.get("Primary Entity") or [])
            primary_actions.update(record_primary_actions)
            primary_entities.update(record_primary_entities)

            # Entspricht der nativen ETL: Trigger- und Target-Aktionen werden
            # ebenfalls als HAS_ACTION-Beziehungen an die Story gebunden.
            all_story_actions = set(record_primary_actions)
            for trigger in record.get("Triggers") or []:
                if len(trigger) >= 2:
                    all_story_actions.add(trigger[1])
            for target in record.get("Targets") or []:
                if len(target) >= 2:
                    all_story_actions.add(target[0])

            benefit = record.get("Benefit")
            has_benefit = benefit is not None and str(benefit).strip() != ""
            if has_benefit:
                benefits.add(str(benefit))

            normalized = normalize_text(record.get("Text", ""))
            story = gt_by_text.get(normalized)
            if story is None:
                unmapped.append(record.get("Text", ""))
                continue
            if not has_benefit:
                missing_benefit.add(story["id"])
            if len(all_story_actions) > 2:
                non_atomic_gt2.add(story["id"])

        if unmapped:
            raise RuntimeError(f"{model}: {len(unmapped)} Texte nicht auf Ground Truth abbildbar")

        report[model] = {
            "primary_field_cardinalities": {
                "Stories": len(records),
                "Personas": len(primary_personas),
                "Actions": len(primary_actions),
                "Entities": len(primary_entities),
                "Benefits": len(benefits),
                "Missing_Benefit_Alarms": len(missing_benefit),
            },
            "missing_benefit": metrics(missing_benefit, expected_missing_benefit),
            "fat_story_actions_gt2": metrics(non_atomic_gt2, expected_non_atomic),
        }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    print(f"LLM-Vergleich gespeichert in: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
