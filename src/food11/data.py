from pathlib import Path
from PIL import Image
import shutil

CATEGORIES = {
    0: "Bread", 1: "Dairy product", 2: "Dessert", 3: "Egg",
    4: "Fried food", 5: "Meat", 6: "Noodles-Pasta", 7: "Rice",
    8: "Seafood", 9: "Soup", 10: "Vegetable-Fruit",
}

RAW_DIR = Path("data/food11_raw")
PROCESSED_DIR = Path("data/food11_processed")
MINI_DIR = Path("data/food11_processed_mini")
SPLITS = ["training", "evaluation", "validation"]
TARGET_SIZE = (128, 128)
MINI_LIMIT = 100


def process_split(split: str, dst_root: Path, limit: int | None):
    src_split_dir = RAW_DIR / split
    counts = {cat_id: 0 for cat_id in CATEGORIES}

    for img_path in sorted(src_split_dir.glob("*.jpg")):
        cat_id = int(img_path.stem.split("_")[0])
        if cat_id not in CATEGORIES:
            continue
        if limit is not None and counts[cat_id] >= limit:
            continue

        cat_name = CATEGORIES[cat_id]
        dst_dir = dst_root / split / cat_name
        dst_dir.mkdir(parents=True, exist_ok=True)

        with Image.open(img_path) as im:
            im = im.resize(TARGET_SIZE)
            im.save(dst_dir / img_path.name)

        counts[cat_id] += 1

    print(f"{dst_root.name}/{split}: {counts}")


def main():
    for split in SPLITS:
        process_split(split, PROCESSED_DIR, limit=None)
        process_split(split, MINI_DIR, limit=MINI_LIMIT)


if __name__ == "__main__":
    main()