import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import torch
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix
)

from models.factory import build_model, MODES
from preprocessing.dataset import create_dataloaders


# --------------------------------------------------
# 1. Configuration
# --------------------------------------------------

DATA_DIR = "data/beans"
RESULTS_DIR = "results"

BATCH_SIZE = 8
NUM_WORKERS = 0

CLASS_NAMES = [
    "angular_leaf_spot",
    "bean_rust",
    "healthy"
]


def parse_args():

    parser = argparse.ArgumentParser(description="Evaluate the PVT + GCADSN baseline / ablations / MSCAF-Net")

    parser.add_argument(
        "--mode",
        choices=list(MODES),
        default="fused"
    )

    parser.add_argument("--checkpoint", type=str, default=None)

    parser.add_argument(
        "--tag",
        type=str,
        default="",
        help="Suffix used at training time (e.g. --tag s1); selects the matching checkpoint and output names"
    )

    return parser.parse_args()


def main():

    args = parse_args()

    suffix = f"_{args.tag}" if args.tag else ""

    checkpoint_path = args.checkpoint or f"checkpoints/baseline_{args.mode}{suffix}_best.pth"

    os.makedirs(RESULTS_DIR, exist_ok=True)

    # --------------------------------------------------
    # 2. Select device
    # --------------------------------------------------

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    print("Device:", device)

    if torch.cuda.is_available():
        print("GPU:", torch.cuda.get_device_name(0))

    # --------------------------------------------------
    # 3. Load test dataset (always the original, unaugmented split)
    # --------------------------------------------------

    _, _, test_loader, _, _, test_dataset = create_dataloaders(
        data_dir=DATA_DIR,
        augmented_dir=None,
        image_size=224,
        batch_size=BATCH_SIZE,
        num_workers=NUM_WORKERS
    )

    print("\nTest images:", len(test_dataset))
    print("Classes:", test_dataset.classes)

    # --------------------------------------------------
    # 4. Create model
    # --------------------------------------------------

    checkpoint = torch.load(
        checkpoint_path,
        map_location=device,
        weights_only=False
    )

    # MSCAF-Net checkpoints carry their own architecture options;
    # the base-paper checkpoints have none (defaults apply).
    model_config = checkpoint.get("model_config") or {}

    # Weights come from the checkpoint, so skip the pretrained download.
    model = build_model(
        args.mode,
        num_classes=3,
        pretrained=False,
        mscaf_kwargs=model_config.get("mscaf_kwargs")
    )

    model = model.to(device)

    # --------------------------------------------------
    # 5. Load trained weights
    # --------------------------------------------------

    model.load_state_dict(
        checkpoint["model_state_dict"]
    )

    print("\nLoaded checkpoint:", checkpoint_path)
    print("Epoch:", checkpoint["epoch"])

    # --------------------------------------------------
    # 6. Evaluation mode
    # --------------------------------------------------

    model.eval()

    all_labels = []
    all_predictions = []

    # --------------------------------------------------
    # 7. Test the model
    # --------------------------------------------------

    with torch.no_grad():

        for images, labels in test_loader:

            images = images.to(device)
            labels = labels.to(device)

            outputs = model(images)

            predictions = torch.argmax(
                outputs,
                dim=1
            )

            all_labels.extend(
                labels.cpu().numpy()
            )

            all_predictions.extend(
                predictions.cpu().numpy()
            )

    # --------------------------------------------------
    # 8. Calculate metrics
    # --------------------------------------------------

    accuracy = accuracy_score(
        all_labels,
        all_predictions
    )

    precision = precision_score(
        all_labels,
        all_predictions,
        average="weighted",
        zero_division=0
    )

    recall = recall_score(
        all_labels,
        all_predictions,
        average="weighted",
        zero_division=0
    )

    f1 = f1_score(
        all_labels,
        all_predictions,
        average="weighted",
        zero_division=0
    )

    # --------------------------------------------------
    # 9. Print results
    # --------------------------------------------------

    print("\n" + "=" * 50)
    print(f"{args.mode.upper()} MODEL TEST RESULTS")
    print("=" * 50)

    print(f"Accuracy : {accuracy * 100:.2f}%")
    print(f"Precision: {precision * 100:.2f}%")
    print(f"Recall   : {recall * 100:.2f}%")
    print(f"F1 Score : {f1 * 100:.2f}%")

    # --------------------------------------------------
    # 10. Classification report
    # --------------------------------------------------

    report_text = classification_report(
        all_labels,
        all_predictions,
        target_names=CLASS_NAMES,
        digits=4,
        zero_division=0
    )

    print("\nClassification Report:")
    print(report_text)

    # --------------------------------------------------
    # 11. Confusion matrix
    # --------------------------------------------------

    cm = confusion_matrix(
        all_labels,
        all_predictions
    )

    print("\nConfusion Matrix:")
    print(cm)

    # --------------------------------------------------
    # 12. Persist results to results/
    # --------------------------------------------------

    metrics = {
        "mode": args.mode,
        "checkpoint": checkpoint_path,
        "checkpoint_epoch": checkpoint["epoch"],
        "model_config": model_config,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_matrix": cm.tolist(),
        "class_names": CLASS_NAMES
    }

    metrics_path = os.path.join(RESULTS_DIR, f"test_metrics_{args.mode}{suffix}.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    report_path = os.path.join(RESULTS_DIR, f"classification_report_{args.mode}{suffix}.txt")
    with open(report_path, "w") as f:
        f.write(report_text)

    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(
        cm, annot=True, fmt="d", cmap="Blues",
        xticklabels=CLASS_NAMES, yticklabels=CLASS_NAMES, ax=ax
    )
    ax.set_xlabel("Predicted Label")
    ax.set_ylabel("True Label")
    ax.set_title(f"Confusion Matrix — {args.mode}")
    plt.tight_layout()
    cm_path = os.path.join(RESULTS_DIR, f"confusion_matrix_{args.mode}{suffix}.png")
    plt.savefig(cm_path, dpi=150)
    plt.close(fig)

    print("\nSaved:", metrics_path)
    print("Saved:", report_path)
    print("Saved:", cm_path)


if __name__ == "__main__":
    main()
