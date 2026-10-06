import argparse

import torch
from torch import nn, optim
from torch.utils.data import DataLoader
from torchvision.datasets import ImageFolder

from models.mscaf_net import MSCAFNet
from preprocessing.transforms import get_train_transforms, get_eval_transforms


def parse_args():
    parser = argparse.ArgumentParser(description="Train MSCAF-Net")
    parser.add_argument("--data-dir", type=str, default="data/beans")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--num-classes", type=int, default=3)
    parser.add_argument("--checkpoint-dir", type=str, default="checkpoints")
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    return parser.parse_args()


def train(args):
    train_dataset = ImageFolder(f"{args.data_dir}/train", transform=get_train_transforms())
    val_dataset = ImageFolder(f"{args.data_dir}/validation", transform=get_eval_transforms())

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False)

    model = MSCAFNet(num_classes=args.num_classes).to(args.device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=args.lr)

    for epoch in range(args.epochs):
        model.train()
        running_loss = 0.0
        for images, labels in train_loader:
            images, labels = images.to(args.device), labels.to(args.device)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item()

        print(f"Epoch {epoch + 1}/{args.epochs} - loss: {running_loss / len(train_loader):.4f}")


if __name__ == "__main__":
    train(parse_args())
