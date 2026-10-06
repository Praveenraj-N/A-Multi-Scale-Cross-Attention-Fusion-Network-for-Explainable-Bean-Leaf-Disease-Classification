import argparse

import torch
from torch.utils.data import DataLoader
from torchvision.datasets import ImageFolder

from models.mscaf_net import MSCAFNet
from preprocessing.transforms import get_eval_transforms
from evaluation.metrics import compute_metrics


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate MSCAF-Net")
    parser.add_argument("--data-dir", type=str, default="data/beans")
    parser.add_argument("--checkpoint", type=str, required=True)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--num-classes", type=int, default=3)
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    return parser.parse_args()


def evaluate(args):
    test_dataset = ImageFolder(f"{args.data_dir}/test", transform=get_eval_transforms())
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False)

    model = MSCAFNet(num_classes=args.num_classes).to(args.device)
    model.load_state_dict(torch.load(args.checkpoint, map_location=args.device))
    model.eval()

    y_true, y_pred = [], []
    with torch.no_grad():
        for images, labels in test_loader:
            images = images.to(args.device)
            outputs = model(images)
            preds = outputs.argmax(dim=1).cpu().numpy()

            y_true.extend(labels.numpy())
            y_pred.extend(preds)

    metrics = compute_metrics(y_true, y_pred)
    print(metrics)
    return metrics


if __name__ == "__main__":
    evaluate(parse_args())
