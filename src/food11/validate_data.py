import argparse
import hashlib
import io
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image

CLASSES = [
    "Bread", "Dairy product", "Dessert", "Egg", "Fried food", "Meat",
    "Noodles-Pasta", "Rice", "Seafood", "Soup", "Vegetable-Fruit",
]
SPLITS = ["training", "validation", "evaluation"]
EXPECTED_SIZE = (128, 128)
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def main():
    parser = argparse.ArgumentParser(description="Validate a processed Food-11 dataset.")
    parser.add_argument("root", type=Path, help="e.g. data/food11_processed_mini")
    parser.add_argument("--min-per-class", type=int, default=50)
    parser.add_argument("--tau", type=float, default=0.05)
    args = parser.parse_args()

    if not args.root.is_dir():
        print(f"FAIL  dataset folder not found: {args.root}")
        sys.exit(1)

    failures = []

    def report(ok, message, details=()):
        print(f"{'PASS' if ok else 'FAIL'}  {message}")
        if not ok:
            for line in details[:5]:
                print(f"        {line}")
            if len(details) > 5:
                print(f"        ... and {len(details) - 5} more")
            failures.append(message)

    # Read every image once: count it, check it, hash it.
    counts = {split: {} for split in SPLITS}
    bad_images = []
    hashes = defaultdict(list)
    class_problems = []

    for split in SPLITS:
        split_dir = args.root / split
        found = set()
        if split_dir.is_dir():
            found = {p.name for p in split_dir.iterdir() if p.is_dir()}
        missing = sorted(set(CLASSES) - found)
        extra = sorted(found - set(CLASSES))
        if not split_dir.is_dir():
            class_problems.append(f"{split}: folder missing")
        if missing:
            class_problems.append(f"{split}: missing classes {missing}")
        if extra:
            class_problems.append(f"{split}: unexpected folders {extra}")

        for class_name in sorted(found & set(CLASSES)):
            images = [
                p for p in (split_dir / class_name).iterdir()
                if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
            ]
            counts[split][class_name] = len(images)
            for path in images:
                data = path.read_bytes()
                hashes[hashlib.md5(data).hexdigest()].append((split, path))
                try:
                    with Image.open(io.BytesIO(data)) as im:
                        im.load()
                        if im.mode != "RGB" or im.size != EXPECTED_SIZE:
                            bad_images.append(f"{path}: mode={im.mode} size={im.size}")
                except (OSError, ValueError, SyntaxError) as exc:
                    bad_images.append(f"{path}: cannot open ({exc})")

    # 1. each split has exactly the 11 class folders
    report(not class_problems, "each split contains exactly the 11 class folders", class_problems)

    # 2. every image opens, is RGB and 128x128
    report(not bad_images, "every image opens, is RGB and 128x128", bad_images)

    # 3. minimum images per class
    too_few = [
        f"{split}/{class_name}: {counts[split].get(class_name, 0)} < {args.min_per_class}"
        for split in SPLITS
        for class_name in CLASSES
        if counts[split].get(class_name, 0) < args.min_per_class
    ]
    report(not too_few, f"every class has at least {args.min_per_class} images per split", too_few)

    # 4. no image appears in two splits
    leaks = []
    for entries in hashes.values():
        if len({split for split, _ in entries} - {None}) > 1:
            leaks.append(" == ".join(str(path) for _, path in entries))
    report(not leaks, "no image appears in two splits", leaks)

    # 5. class shares of training vs validation within tau
    train_total = sum(counts["training"].values())
    val_total = sum(counts["validation"].values())
    drift = []
    if train_total == 0 or val_total == 0:
        drift.append("training or validation split is empty")
    else:
        for class_name in CLASSES:
            train_share = counts["training"].get(class_name, 0) / train_total
            val_share = counts["validation"].get(class_name, 0) / val_total
            if abs(train_share - val_share) > args.tau:
                drift.append(
                    f"{class_name}: train {train_share:.3f} vs val {val_share:.3f}"
                )
    report(not drift, f"class shares training vs validation within tau={args.tau}", drift)

    if failures:
        print(f"\n{len(failures)} check(s) failed")
        sys.exit(1)
    print("\nall checks passed")


if __name__ == "__main__":
    main()
