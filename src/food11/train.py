import argparse
import mlflow
import mlflow.pytorch
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms


def get_dataloaders(dataset_name: str, batch_size: int):
    root = "data/food11_processed_mini" if dataset_name == "mini" else "data/food11_processed"

    transform = transforms.Compose([
        transforms.Resize((128, 128)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    train_ds = datasets.ImageFolder(f"{root}/training", transform=transform)
    val_ds = datasets.ImageFolder(f"{root}/validation", transform=transform)
    test_ds = datasets.ImageFolder(f"{root}/evaluation", transform=transform)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    return train_loader, val_loader, test_loader, len(train_ds.classes)


def build_model(num_classes: int):
    model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
    model.fc = nn.Linear(model.fc.in_features, num_classes)
    return model


def evaluate(model, loader, criterion, device):
    model.eval()
    total_loss, correct, total = 0.0, 0, 0
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            out = model(x)
            loss = criterion(out, y)
            total_loss += loss.item() * x.size(0)
            correct += (out.argmax(1) == y).sum().item()
            total += x.size(0)
    return total_loss / total, correct / total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["processed", "mini"], default="mini")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    train_loader, val_loader, test_loader, num_classes = get_dataloaders(args.dataset, args.batch_size)

    model = build_model(num_classes).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    mlflow.set_tracking_uri("http://127.0.0.1:5000")
    mlflow.set_experiment("food11")

    with mlflow.start_run():
        mlflow.log_params({
            "dataset": args.dataset,
            "epochs": args.epochs,
            "lr": args.lr,
            "batch_size": args.batch_size,
            "model": "resnet18",
        })

        for epoch in range(args.epochs):
            model.train()
            running_loss, total = 0.0, 0
            for x, y in train_loader:
                x, y = x.to(device), y.to(device)
                optimizer.zero_grad()
                out = model(x)
                loss = criterion(out, y)
                loss.backward()
                optimizer.step()
                running_loss += loss.item() * x.size(0)
                total += x.size(0)

            train_loss = running_loss / total
            val_loss, val_accuracy = evaluate(model, val_loader, criterion, device)

            print(f"epoch {epoch}: train_loss={train_loss:.4f} val_loss={val_loss:.4f} val_accuracy={val_accuracy:.4f}")

            mlflow.log_metric("train_loss", train_loss, step=epoch)
            mlflow.log_metric("val_loss", val_loss, step=epoch)
            mlflow.log_metric("val_accuracy", val_accuracy, step=epoch)

        test_loss, test_accuracy = evaluate(model, test_loader, criterion, device)
        print(f"final test_accuracy={test_accuracy:.4f}")
        mlflow.log_metric("test_accuracy", test_accuracy)

        example_input = next(iter(train_loader))[0][:1].cpu().numpy()
        mlflow.pytorch.log_model(model, "model", input_example=example_input, serialization_format="pickle")


if __name__ == "__main__":
    main()