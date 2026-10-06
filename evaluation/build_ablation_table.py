"""Collects results/test_metrics_*.json (produced by evaluate_baseline.py for
each trained model) into a single comparison table: the base paper's
ablation (Table 4: PVT / CNN / Proposed Network) followed by every
MSCAF-Net variant found. Extra runs (seeds, MSCAF-Net ablations) are picked
up automatically from their --tag suffix."""

import csv
import glob
import json
import os

RESULTS_DIR = "results"

BASE_ORDER = ["pvt", "gcadsn", "fused", "mscaf"]

LABELS = {
    "pvt": "PVT only",
    "gcadsn": "GCADSN only",
    "fused": "PVT + GCADSN (base paper)",
    "mscaf": "MSCAF-Net"
}


def describe_mscaf(config):
    """Short description of an MSCAF-Net variant from its saved options."""

    kwargs = (config or {}).get("mscaf_kwargs") or {}

    if not kwargs:
        return ""

    scales = "/".join(str(s) for s in kwargs.get("scales", []))
    cross = "cross-attn" if kwargs.get("use_cross_attention", True) else "no cross-attn"
    fusion = kwargs.get("fusion", "adaptive")

    return f" [scales {scales}, {cross}, {fusion} fusion]"


def main():

    entries = []

    for path in sorted(glob.glob(os.path.join(RESULTS_DIR, "test_metrics_*.json"))):

        with open(path) as f:
            metrics = json.load(f)

        mode = metrics["mode"]

        stem = os.path.basename(path)[len("test_metrics_"):-len(".json")]
        tag = stem[len(mode):].lstrip("_")

        label = LABELS.get(mode, mode)

        if mode == "mscaf":
            label += describe_mscaf(metrics.get("model_config"))

        if tag:
            label += f" ({tag})"

        entries.append((BASE_ORDER.index(mode) if mode in BASE_ORDER else 99, tag, {
            "Model": label,
            "Accuracy (%)": round(metrics["accuracy"] * 100, 2),
            "Precision (%)": round(metrics["precision"] * 100, 2),
            "Recall (%)": round(metrics["recall"] * 100, 2),
            "F1 (%)": round(metrics["f1"] * 100, 2),
        }))

    if not entries:
        print("No metrics found. Nothing to write (run evaluate_baseline.py first).")
        return

    rows = [row for _, _, row in sorted(entries, key=lambda e: (e[0], e[1]))]

    out_path = os.path.join(RESULTS_DIR, "ablation_table.csv")

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print("Ablation table:")
    header = list(rows[0].keys())
    print(" | ".join(header))
    for row in rows:
        print(" | ".join(str(row[k]) for k in header))

    print("\nSaved:", out_path)


if __name__ == "__main__":
    main()
