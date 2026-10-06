"""Produces the Grad-CAM visualization grid the paper shows in Table 5:
one original/heatmap-overlay pair per class, using the trained fused
PVT+GCADSN model. Target layer is `model.fusion_identity`, the hook point
inserted right after the two branches are concatenated (there is no
regular conv layer after fusion, since GAP follows immediately).
"""

import os

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from torchvision import transforms

import argparse

from models.factory import build_model, MODES
from explainability.gradcam import GradCAM
from preprocessing.dataset import create_dataloaders
from preprocessing.transforms import IMAGENET_MEAN, IMAGENET_STD


DATA_DIR = "data/beans"
RESULTS_DIR = "results"

CLASS_NAMES = [
    "angular_leaf_spot",
    "bean_rust",
    "healthy"
]


def denormalize(tensor):
    mean = torch.tensor(IMAGENET_MEAN).view(3, 1, 1)
    std = torch.tensor(IMAGENET_STD).view(3, 1, 1)
    image = tensor.cpu() * std + mean
    image = image.clamp(0, 1).permute(1, 2, 0).numpy()
    return (image * 255).astype(np.uint8)


def overlay_heatmap(image_rgb, cam, alpha=0.4):
    heatmap = cv2.applyColorMap((cam * 255).astype(np.uint8), cv2.COLORMAP_JET)
    heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
    overlay = (alpha * heatmap + (1 - alpha) * image_rgb).astype(np.uint8)
    return overlay


def parse_args():

    parser = argparse.ArgumentParser(description="Grad-CAM grid for a trained model")
    parser.add_argument("--mode", choices=list(MODES), default="fused",
                        help="fused = base paper network, mscaf = MSCAF-Net")
    parser.add_argument("--tag", type=str, default="",
                        help="Suffix used at training time (selects the checkpoint)")
    return parser.parse_args()


def main():

    args = parse_args()

    suffix = f"_{args.tag}" if args.tag else ""

    checkpoint_path = f"checkpoints/baseline_{args.mode}{suffix}_best.pth"

    # Keep the original file name for the base-paper network
    out_name = "gradcam_grid.png" if args.mode == "fused" and not args.tag else f"gradcam_grid_{args.mode}{suffix}.png"

    os.makedirs(RESULTS_DIR, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)

    model_config = checkpoint.get("model_config") or {}

    model = build_model(
        args.mode,
        num_classes=3,
        pretrained=False,
        mscaf_kwargs=model_config.get("mscaf_kwargs")
    ).to(device)

    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    gradcam = GradCAM(model, model.fusion_identity)

    _, _, test_loader, _, _, test_dataset = create_dataloaders(
        data_dir=DATA_DIR,
        augmented_dir=None,
        image_size=224,
        batch_size=1,
        num_workers=0
    )

    samples_by_class = {}

    for image, label in test_dataset:
        label = int(label)
        if label not in samples_by_class:
            samples_by_class[label] = image
        if len(samples_by_class) == len(CLASS_NAMES):
            break

    fig, axes = plt.subplots(2, len(CLASS_NAMES), figsize=(4 * len(CLASS_NAMES), 8))

    for col, class_idx in enumerate(sorted(samples_by_class.keys())):

        image_tensor = samples_by_class[class_idx].unsqueeze(0).to(device)

        cam = gradcam.generate(image_tensor, class_idx=class_idx)

        image_rgb = denormalize(image_tensor[0])
        overlay = overlay_heatmap(image_rgb, cam)

        axes[0, col].imshow(image_rgb)
        axes[0, col].set_title(f"Original: {CLASS_NAMES[class_idx]}")
        axes[0, col].axis("off")

        axes[1, col].imshow(overlay)
        axes[1, col].set_title("Grad-CAM")
        axes[1, col].axis("off")

    plt.tight_layout()
    out_path = os.path.join(RESULTS_DIR, out_name)
    plt.savefig(out_path, dpi=150)
    plt.close(fig)

    print("Saved:", out_path)


if __name__ == "__main__":
    main()
