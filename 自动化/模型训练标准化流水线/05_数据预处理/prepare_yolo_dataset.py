import argparse
import json
import random
import shutil
from collections import Counter
from pathlib import Path


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def load_result(record):
    result = record.get("result", "{}")
    return json.loads(result) if isinstance(result, str) else result


def iter_rect_boxes(result):
    for ann in result.get("annotations", []):
        if ann.get("toolName") != "rectTool":
            continue
        for box in ann.get("result", []):
            yield box


def clamp(value, low, high):
    return max(low, min(high, value))


def yolo_line(box, width, height, class_to_id):
    label = str(box.get("label", "")).strip()
    if not label or label not in class_to_id:
        return None

    x = float(box.get("x", 0))
    y = float(box.get("y", 0))
    w = float(box.get("width", 0))
    h = float(box.get("height", 0))

    xmin = clamp(x, 0.0, float(width))
    ymin = clamp(y, 0.0, float(height))
    xmax = clamp(x + w, 0.0, float(width))
    ymax = clamp(y + h, 0.0, float(height))
    bw = xmax - xmin
    bh = ymax - ymin
    if bw <= 0 or bh <= 0 or width <= 0 or height <= 0:
        return None

    cx = (xmin + xmax) / 2.0 / width
    cy = (ymin + ymax) / 2.0 / height
    nw = bw / width
    nh = bh / height
    return f"{class_to_id[label]} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}"


def write_yaml(path, dataset_dir, names, include_test=True):
    lines = [
        f"path: {dataset_dir.as_posix()}",
        "train: images/train",
        "val: images/val",
    ]
    if include_test:
        lines.append("test: images/test")
    lines.extend([
        f"nc: {len(names)}",
        "names:",
    ])
    lines.extend(f"  {idx}: {name}" for idx, name in enumerate(names))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Convert exported LabelU records to YOLOv11 dataset.")
    parser.add_argument("--labelu-json", default="./raw/export_labelu.json")
    parser.add_argument("--images-dir", default="./raw/images")
    parser.add_argument("--output", default="./dataset")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--min-count", type=int, default=1)
    args = parser.parse_args()

    labelu_json = Path(args.labelu_json).resolve()
    images_dir = Path(args.images_dir).resolve()
    output_dir = Path(args.output).resolve()

    records = json.loads(labelu_json.read_text(encoding="utf-8"))
    class_counts = Counter()
    usable = []

    for record in records:
        result = load_result(record)
        filename = record.get("fileName")
        if not filename:
            continue
        image_path = images_dir / filename
        if not image_path.exists() or image_path.suffix.lower() not in IMAGE_EXTS:
            continue
        labels = []
        for box in iter_rect_boxes(result):
            label = str(box.get("label", "")).strip()
            if label:
                class_counts[label] += 1
                labels.append(label)
        usable.append(record)

    names = sorted([name for name, count in class_counts.items() if count >= args.min_count])
    if not names:
        raise SystemExit("No classes found. Check raw/export_labelu.json and raw/images.")
    class_to_id = {name: idx for idx, name in enumerate(names)}

    random.seed(args.seed)
    random.shuffle(usable)
    total = len(usable)
    train_end = int(total * args.train_ratio)
    val_end = train_end + int(total * args.val_ratio)
    splits = {
        "train": usable[:train_end],
        "val": usable[train_end:val_end],
        "test": usable[val_end:],
    }

    if output_dir.exists():
        shutil.rmtree(output_dir)
    for split in splits:
        (output_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    stats = {"classes": class_counts, "splits": {k: len(v) for k, v in splits.items()}, "skipped_empty": 0}
    for split, split_records in splits.items():
        for record in split_records:
            result = load_result(record)
            width = int(float(result.get("width", 0) or 0))
            height = int(float(result.get("height", 0) or 0))
            filename = record["fileName"]
            src_img = images_dir / filename
            dst_img = output_dir / "images" / split / filename
            shutil.copy2(src_img, dst_img)

            lines = []
            for box in iter_rect_boxes(result):
                line = yolo_line(box, width, height, class_to_id)
                if line:
                    lines.append(line)
            if not lines:
                stats["skipped_empty"] += 1
            label_path = output_dir / "labels" / split / f"{Path(filename).stem}.txt"
            label_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    write_yaml(output_dir / "dataset.yaml", output_dir, names)
    (output_dir / "class_counts.json").write_text(
        json.dumps(class_counts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "prepare_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"dataset={output_dir}")
    print(f"images={total} classes={len(names)}")
    print(f"splits={stats['splits']}")


if __name__ == "__main__":
    main()
