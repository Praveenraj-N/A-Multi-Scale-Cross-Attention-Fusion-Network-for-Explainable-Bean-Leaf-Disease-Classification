import argparse
import csv
import math
import os
import random
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn

from torch.optim import RAdam
from torch.optim.lr_scheduler import LambdaLR
from tqdm import tqdm

from preprocessing.dataset import create_dataloaders
from models.factory import build_model, MODES


# =========================================================
# Configuration
# =========================================================

DATA_DIR = "data/beans"
AUGMENTED_DIR = "data/beans_augmented"

NUM_CLASSES = 3

CHECKPOINT_DIR = "checkpoints"
RESULTS_DIR = "results"


# =========================================================
# Reproducibility
# =========================================================

def set_seed(seed):

    random.seed(seed)

    np.random.seed(seed)

    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# =========================================================
# Calculate accuracy
# =========================================================

def calculate_accuracy(logits, labels):

    predictions = torch.argmax(
        logits,
        dim=1
    )

    correct = (
        predictions == labels
    ).sum().item()

    total = labels.size(0)

    return correct / total


# =========================================================
# Argument parsing
# =========================================================

def parse_args():

    parser = argparse.ArgumentParser(description="Train the PVT + GCADSN baseline / ablations")

    parser.add_argument(
        "--mode",
        choices=list(MODES),
        default="fused",
        help="fused = base paper PVT+GCADSN, pvt/gcadsn = single-track ablation, "
             "mscaf = MSCAF-Net (multi-scale + cross-attention + adaptive fusion)"
    )

    # MSCAF-Net options (only used with --mode mscaf). The ablation
    # ladder is: --mscaf-scales 7 --fusion concat --no-cross-attention
    # (~base paper), then add multi-scale, then cross-attention, then
    # adaptive fusion. Run each with its own --tag.
    parser.add_argument("--mscaf-scales", type=str, default="28,14,7",
                        help="comma-separated feature-map resolutions to fuse (any of 28,14,7)")
    parser.add_argument("--mscaf-dim", type=int, default=128)
    parser.add_argument("--mscaf-heads", type=int, default=4)
    parser.add_argument("--no-cross-attention", action="store_true")
    parser.add_argument("--fusion", choices=["adaptive", "concat"], default="adaptive")
    parser.add_argument("--mscaf-dropout", type=float, default=0.1)

    parser.add_argument("--epochs", type=int, default=50)

    # Paper's tuned optimum (Table 2) is batch size 32, but that needs
    # ~5.3GB of VRAM for this model and a 4GB GPU can't hold it. On a
    # small GPU keep a small physical batch and accumulate gradients to
    # reach the same effective batch size of 32. On a 16GB GPU (Kaggle /
    # Colab) pass --physical-batch-size 32 --accumulation-steps 1.
    parser.add_argument("--physical-batch-size", type=int, default=8)
    parser.add_argument("--accumulation-steps", type=int, default=4)

    # Paper's tuned lr / weight decay (Table 2). The pretrained PVT
    # backbone is fine-tuned at a lower rate (--backbone-lr): 1e-3 is
    # too aggressive for pretrained transformer weights and made the
    # validation accuracy swing by several points between epochs.
    parser.add_argument("--lr", type=float, default=1e-3,
                        help="lr for everything except the PVT backbone (GCADSN, projection, classifier)")
    parser.add_argument("--backbone-lr", type=float, default=1e-4,
                        help="lr for the pretrained PVT backbone")
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--warmup-epochs", type=int, default=1)

    # The paper trains a fixed 50 epochs. The default patience is large
    # enough that early stopping never triggers within 50 epochs; lower
    # it only for quick experiments. (GCADSN is trained from scratch and
    # was still improving when an 8-epoch patience cut it off.)
    parser.add_argument(
        "--patience",
        type=int,
        default=50,
        help="Stop early if the validation score does not improve for this many consecutive epochs"
    )

    parser.add_argument(
        "--no-augmented-dir",
        action="store_true",
        help="Disable the offline-augmented dataset and fall back to online augmentation"
    )

    parser.add_argument(
        "--augmented-validation",
        action="store_true",
        help="Validate on the offline-augmented validation copies (paper's setup) "
             "instead of the original 133 validation photos"
    )

    parser.add_argument("--no-amp", action="store_true", help="Disable mixed-precision training")

    parser.add_argument("--num-workers", type=int, default=0,
                        help="DataLoader workers (0 on Windows; 2-4 on Kaggle/Colab)")

    parser.add_argument("--seed", type=int, default=42)

    parser.add_argument(
        "--tag",
        type=str,
        default="",
        help="Suffix for checkpoint / log file names (e.g. --tag s1 for a second seed)"
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Continue from the last saved epoch if a *_last.pth checkpoint exists"
    )

    return parser.parse_args()


# =========================================================
# Main
# =========================================================

def main():

    args = parse_args()

    set_seed(args.seed)

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    suffix = f"_{args.tag}" if args.tag else ""

    checkpoint_path = os.path.join(CHECKPOINT_DIR, f"baseline_{args.mode}{suffix}_best.pth")
    last_path = os.path.join(CHECKPOINT_DIR, f"baseline_{args.mode}{suffix}_last.pth")
    log_path = os.path.join(RESULTS_DIR, f"training_log_{args.mode}{suffix}.csv")
    curves_path = os.path.join(RESULTS_DIR, f"training_curves_{args.mode}{suffix}.png")

    augmented_dir = None if args.no_augmented_dir else AUGMENTED_DIR

    use_amp = device.type == "cuda" and not args.no_amp

    print("===================================")
    print(f"       BASELINE TRAINING [{args.mode.upper()}]")
    print("===================================")

    print("\nDevice:", device)

    if torch.cuda.is_available():

        print(
            "GPU:",
            torch.cuda.get_device_name(0)
        )

    effective_batch_size = args.physical_batch_size * args.accumulation_steps

    print("\nConfiguration:")
    print("Physical batch size:", args.physical_batch_size)
    print("Accumulation steps:", args.accumulation_steps)
    print("Effective batch size:", effective_batch_size, "(paper's tuned optimum: 32)")
    print("Epochs:", args.epochs)
    print("Learning rate:", args.lr)
    print("Backbone learning rate:", args.backbone_lr)
    print("Weight decay:", args.weight_decay)
    print("Warmup epochs:", args.warmup_epochs)
    print("Patience:", args.patience)
    print("Mixed precision:", use_amp)
    print("Seed:", args.seed)
    print("Augmented dir:", augmented_dir)
    print("Validation set:", "augmented" if args.augmented_validation else "original")

    # -----------------------------------------------------
    # Data
    # -----------------------------------------------------

    (
        train_loader,
        validation_loader,
        test_loader,
        train_dataset,
        validation_dataset,
        test_dataset
    ) = create_dataloaders(
        data_dir=DATA_DIR,
        augmented_dir=augmented_dir,
        image_size=224,
        batch_size=args.physical_batch_size,
        num_workers=args.num_workers,
        original_validation=not args.augmented_validation
    )

    print("\nDataset:")
    print("Train:", len(train_dataset))
    print("Validation:", len(validation_dataset))
    print("Test:", len(test_dataset))

    # -----------------------------------------------------
    # Model
    # -----------------------------------------------------

    mscaf_kwargs = None

    if args.mode == "mscaf":

        mscaf_kwargs = {
            "scales": [int(s) for s in args.mscaf_scales.split(",")],
            "dim": args.mscaf_dim,
            "num_heads": args.mscaf_heads,
            "use_cross_attention": not args.no_cross_attention,
            "fusion": args.fusion,
            "dropout": args.mscaf_dropout
        }

        print("\nMSCAF-Net config:", mscaf_kwargs)

    # Stored in the checkpoints so evaluation / Grad-CAM can rebuild the
    # exact same architecture without repeating the command-line options.
    model_config = {
        "mode": args.mode,
        "mscaf_kwargs": mscaf_kwargs
    }

    model = build_model(
        args.mode,
        num_classes=NUM_CLASSES,
        pretrained=True,
        mscaf_kwargs=mscaf_kwargs
    )

    model = model.to(device)

    print(
        "Parameters:",
        f"{sum(p.numel() for p in model.parameters()) / 1e6:.2f}M"
    )

    # -----------------------------------------------------
    # Loss
    # -----------------------------------------------------

    criterion = nn.CrossEntropyLoss()

    # -----------------------------------------------------
    # Optimizer (lower lr for the pretrained PVT backbone)
    # -----------------------------------------------------

    backbone_params = list(model.pvt.parameters()) if model.pvt is not None else []
    backbone_ids = {id(p) for p in backbone_params}
    other_params = [p for p in model.parameters() if id(p) not in backbone_ids]

    param_groups = []

    if backbone_params:
        param_groups.append({"params": backbone_params, "lr": args.backbone_lr})

    param_groups.append({"params": other_params, "lr": args.lr})

    optimizer = RAdam(
        param_groups,
        weight_decay=args.weight_decay
    )

    # -----------------------------------------------------
    # LR schedule: linear warmup, then cosine decay to 1% of base lr.
    # Stepped once per optimizer update.
    # -----------------------------------------------------

    steps_per_epoch = math.ceil(len(train_loader) / args.accumulation_steps)
    total_steps = steps_per_epoch * args.epochs
    warmup_steps = steps_per_epoch * args.warmup_epochs

    def lr_lambda(step):

        if warmup_steps > 0 and step < warmup_steps:
            return (step + 1) / warmup_steps

        progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)

        return 0.01 + 0.99 * 0.5 * (1.0 + math.cos(math.pi * min(1.0, progress)))

    scheduler = LambdaLR(optimizer, lr_lambda)

    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    # -----------------------------------------------------
    # Create output directories
    # -----------------------------------------------------

    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    best_validation_accuracy = 0.0
    best_validation_loss = float("inf")
    epochs_without_improvement = 0

    history = {
        "train_loss": [],
        "train_accuracy": [],
        "val_loss": [],
        "val_accuracy": []
    }

    start_epoch = 0

    # -----------------------------------------------------
    # Resume (Kaggle / Colab sessions can be cut off)
    # -----------------------------------------------------

    if args.resume and os.path.exists(last_path):

        state = torch.load(last_path, map_location=device, weights_only=False)

        model.load_state_dict(state["model_state_dict"])
        optimizer.load_state_dict(state["optimizer_state_dict"])
        scheduler.load_state_dict(state["scheduler_state_dict"])
        scaler.load_state_dict(state["scaler_state_dict"])

        history = state["history"]
        best_validation_accuracy = state["best_validation_accuracy"]
        best_validation_loss = state["best_validation_loss"]
        epochs_without_improvement = state["epochs_without_improvement"]
        start_epoch = state["epoch"]

        print(f"\nResumed from {last_path} at epoch {start_epoch}")

    # =====================================================
    # Training loop
    # =====================================================

    for epoch in range(start_epoch, args.epochs):

        print(
            f"\nEpoch [{epoch + 1}/{args.epochs}]"
        )

        # -------------------------------------------------
        # TRAINING
        # -------------------------------------------------

        model.train()

        running_loss = 0.0

        running_accuracy = 0.0

        progress_bar = tqdm(
            train_loader,
            desc="Training",
            dynamic_ncols=True
        )

        optimizer.zero_grad()

        for step, (images, labels) in enumerate(progress_bar):

            images = images.to(
                device,
                non_blocking=True
            )

            labels = labels.to(
                device,
                non_blocking=True
            )

            # Forward pass (mixed precision on GPU)
            with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=use_amp):
                logits = model(images)

            # Calculate loss in fp32 (scaled so accumulated gradients match
            # a single step over the full effective batch)
            loss = criterion(
                logits.float(),
                labels
            ) / args.accumulation_steps

            # Backward pass (accumulates into .grad)
            scaler.scale(loss).backward()

            is_accumulation_boundary = (
                (step + 1) % args.accumulation_steps == 0
                or (step + 1) == len(train_loader)
            )

            if is_accumulation_boundary:

                # Update weights
                scaler.step(optimizer)

                scaler.update()

                optimizer.zero_grad()

                scheduler.step()

            # Metrics
            accuracy = calculate_accuracy(
                logits,
                labels
            )

            running_loss += (
                loss.item() * args.accumulation_steps
            )

            running_accuracy += accuracy

            progress_bar.set_postfix(
                loss=f"{loss.item() * args.accumulation_steps:.4f}",
                acc=f"{accuracy * 100:.2f}%"
            )

        train_loss = (
            running_loss /
            len(train_loader)
        )

        train_accuracy = (
            running_accuracy /
            len(train_loader)
        )

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        model.eval()

        validation_loss = 0.0

        validation_accuracy = 0.0

        with torch.no_grad():

            progress_bar = tqdm(
                validation_loader,
                desc="Validation",
                dynamic_ncols=True
            )

            for images, labels in progress_bar:

                images = images.to(
                    device,
                    non_blocking=True
                )

                labels = labels.to(
                    device,
                    non_blocking=True
                )

                with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=use_amp):
                    logits = model(images)

                loss = criterion(
                    logits.float(),
                    labels
                )

                accuracy = calculate_accuracy(
                    logits,
                    labels
                )

                validation_loss += (
                    loss.item()
                )

                validation_accuracy += accuracy

        val_loss = (
            validation_loss /
            len(validation_loader)
        )

        val_accuracy = (
            validation_accuracy /
            len(validation_loader)
        )

        history["train_loss"].append(train_loss)
        history["train_accuracy"].append(train_accuracy)
        history["val_loss"].append(val_loss)
        history["val_accuracy"].append(val_accuracy)

        print("\nResults:")

        print(
            f"Train Loss: {train_loss:.4f}"
        )

        print(
            f"Train Accuracy: "
            f"{train_accuracy * 100:.2f}%"
        )

        print(
            f"Validation Loss: {val_loss:.4f}"
        )

        print(
            f"Validation Accuracy: "
            f"{val_accuracy * 100:.2f}%"
        )

        # -------------------------------------------------
        # Save best model (highest validation accuracy;
        # ties broken by lower validation loss)
        # -------------------------------------------------

        is_better = (
            val_accuracy > best_validation_accuracy
            or (
                val_accuracy == best_validation_accuracy
                and val_loss < best_validation_loss
            )
        )

        if is_better:

            best_validation_accuracy = val_accuracy

            best_validation_loss = val_loss

            epochs_without_improvement = 0

            torch.save(
                {
                    "epoch": epoch + 1,
                    "mode": args.mode,
                    "model_config": model_config,
                    "model_state_dict": model.state_dict(),
                    "validation_accuracy": val_accuracy,
                    "validation_loss": val_loss
                },
                checkpoint_path
            )

            print(
                "\nBest model saved!"
            )

            print(
                f"Best validation accuracy: "
                f"{val_accuracy * 100:.2f}%"
            )

        else:

            epochs_without_improvement += 1

        # -------------------------------------------------
        # Save the resumable "last" checkpoint after every
        # epoch (written to a temp file first, so a cut-off
        # session can't leave a half-written checkpoint)
        # -------------------------------------------------

        torch.save(
            {
                "epoch": epoch + 1,
                "mode": args.mode,
                "model_config": model_config,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "scheduler_state_dict": scheduler.state_dict(),
                "scaler_state_dict": scaler.state_dict(),
                "history": history,
                "best_validation_accuracy": best_validation_accuracy,
                "best_validation_loss": best_validation_loss,
                "epochs_without_improvement": epochs_without_improvement
            },
            last_path + ".tmp"
        )

        os.replace(last_path + ".tmp", last_path)

        # -------------------------------------------------
        # Persist per-epoch log after every epoch, so a run
        # that is interrupted still leaves usable results
        # -------------------------------------------------

        with open(log_path, "w", newline="") as log_file:

            writer = csv.writer(log_file)

            writer.writerow(
                ["epoch", "train_loss", "train_accuracy", "val_loss", "val_accuracy"]
            )

            for i in range(len(history["train_loss"])):

                writer.writerow([
                    i + 1,
                    history["train_loss"][i],
                    history["train_accuracy"][i],
                    history["val_loss"][i],
                    history["val_accuracy"][i]
                ])

        # -------------------------------------------------
        # Early stopping (effectively off by default: the
        # paper trains a fixed 50 epochs)
        # -------------------------------------------------

        if epochs_without_improvement >= args.patience:

            print(
                f"\nEarly stopping: no improvement for "
                f"{args.patience} epochs."
            )

            break

    print("\n===================================")
    print("       TRAINING COMPLETE")
    print("===================================")

    print(
        f"\nBest validation accuracy: "
        f"{best_validation_accuracy * 100:.2f}%"
    )

    print(
        "\nCheckpoint:",
        checkpoint_path
    )

    # -----------------------------------------------------
    # Save accuracy / loss curves (paper Figure 9 a/b)
    # -----------------------------------------------------

    epochs_range = range(1, len(history["train_loss"]) + 1)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    axes[0].plot(epochs_range, history["train_accuracy"], label="Training accuracy")
    axes[0].plot(epochs_range, history["val_accuracy"], label="Validation accuracy")
    axes[0].set_title(f"Accuracy [{args.mode}]")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Accuracy")
    axes[0].legend()

    axes[1].plot(epochs_range, history["train_loss"], label="Training loss")
    axes[1].plot(epochs_range, history["val_loss"], label="Validation loss")
    axes[1].set_title(f"Loss [{args.mode}]")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Loss")
    axes[1].legend()

    plt.tight_layout()
    plt.savefig(curves_path, dpi=150)
    plt.close(fig)

    print("Training curves saved to:", curves_path)


if __name__ == "__main__":
    main()
