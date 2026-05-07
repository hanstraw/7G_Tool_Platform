import argparse
import csv
import json
import os
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import yaml
from ultralytics import YOLO


SIZE_BINS = [
    ("tiny", 0.0, 0.0004),
    ("small", 0.0004, 0.0025),
    ("medium", 0.0025, 0.04),
    ("large", 0.04, float("inf")),
]


PRIORITY_CLASSES = {"streetVendor_other", "streetVendor_vegetablet", "object_basket"}
PRIORITY_SCENES = {"commercialStreet"}
PRIORITY_ANGLES = {"topView"}
PRIORITY_SIZES = {"tiny", "small"}


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def yolo_to_xyxy(parts, img_w, img_h):
    cid, xc, yc, w, h = parts[:5]
    cid = int(cid)
    xc, yc, w, h = map(float, (xc, yc, w, h))
    x1 = (xc - w / 2) * img_w
    y1 = (yc - h / 2) * img_h
    x2 = (xc + w / 2) * img_w
    y2 = (yc + h / 2) * img_h
    return cid, x1, y1, x2, y2


def box_iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def size_bin(box, img_w, img_h):
    x1, y1, x2, y2 = box
    ratio = max(0.0, x2 - x1) * max(0.0, y2 - y1) / max(1.0, img_w * img_h)
    for name, lo, hi in SIZE_BINS:
        if lo <= ratio < hi:
            return name
    return "unknown"


def parse_scene(xml_path):
    attrs = {
        "sceneType": "unknown",
        "lighting": "unknown",
        "weather": "unknown",
        "quality": "unknown",
        "angle": "unknown",
        "source": "unknown",
    }
    if not xml_path.exists():
        return attrs
    try:
        root = ET.parse(xml_path).getroot()
        extra = root.findtext("extra_annotations")
        if not extra:
            return attrs
        for ann in json.loads(extra):
            if ann.get("toolName") != "tagTool":
                continue
            for item in ann.get("result", []):
                for key, val in item.get("value", {}).items():
                    if key in attrs:
                        attrs[key] = val[0] if isinstance(val, list) and val else str(val)
    except Exception:
        pass
    return attrs


def load_targets(label_path, img_w, img_h):
    targets = []
    if not label_path.exists():
        return targets
    with open(label_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            cid, x1, y1, x2, y2 = yolo_to_xyxy(parts, img_w, img_h)
            targets.append({"idx": idx, "class_id": cid, "box": (x1, y1, x2, y2)})
    return targets


def priority_score(row):
    score = 0
    if row["class_name"] in PRIORITY_CLASSES:
        score += 5
    if row["sceneType"] in PRIORITY_SCENES:
        score += 3
    if row["angle"] in PRIORITY_ANGLES:
        score += 2
    if row["size_bin"] in PRIORITY_SIZES:
        score += 2
    if row["error_type"] == "FN":
        score += 2
    return score


def draw_failure(image_path, out_path, rows):
    img = cv2.imread(str(image_path))
    if img is None:
        return
    for row in rows:
        if not row.get("box"):
            continue
        x1, y1, x2, y2 = [int(float(v)) for v in row["box"].split()]
        color = (0, 0, 255) if row["error_type"] == "FN" else (0, 165, 255)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        label = f"{row['error_type']} {row['class_name']} {row['size_bin']}"
        cv2.putText(img, label, (x1, max(20, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), img)


def mine_split(model, base_dir, split, names, out_dir, conf, iou_thres, max_vis):
    image_dir = base_dir / "data" / "images" / split
    label_dir = base_dir / "data" / "labels" / split
    xml_dir = base_dir / "data" / "labelsxml" / split
    rows = []
    per_image_rows = defaultdict(list)

    image_paths = sorted([p for p in image_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}])
    for image_path in image_paths:
        img = cv2.imread(str(image_path))
        if img is None:
            continue
        img_h, img_w = img.shape[:2]
        stem = image_path.stem
        scene = parse_scene(xml_dir / f"{stem}.xml")
        targets = load_targets(label_dir / f"{stem}.txt", img_w, img_h)
        result = model.predict(str(image_path), imgsz=1280, conf=conf, iou=0.5, device=0, verbose=False)[0]
        preds = []
        for i, box in enumerate(result.boxes):
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            preds.append({
                "idx": i,
                "class_id": int(box.cls[0]),
                "score": float(box.conf[0]),
                "box": (x1, y1, x2, y2),
            })

        used_pred = set()
        for target in targets:
            best_same = (-1.0, None)
            best_any = (-1.0, None)
            for pred in preds:
                if pred["idx"] in used_pred:
                    continue
                val = box_iou(target["box"], pred["box"])
                if val > best_any[0]:
                    best_any = (val, pred)
                if pred["class_id"] == target["class_id"] and val > best_same[0]:
                    best_same = (val, pred)

            cls_name = names[target["class_id"]]
            bin_name = size_bin(target["box"], img_w, img_h)
            if best_same[1] is not None and best_same[0] >= iou_thres:
                used_pred.add(best_same[1]["idx"])
                continue

            err_type = "FN"
            pred_class = ""
            pred_score = ""
            best_iou = best_same[0] if best_same[0] >= 0 else 0.0
            if best_any[1] is not None and best_any[0] >= iou_thres and best_any[1]["class_id"] != target["class_id"]:
                err_type = "CLS_MISMATCH"
                pred_class = names[best_any[1]["class_id"]]
                pred_score = f"{best_any[1]['score']:.4f}"
                best_iou = best_any[0]

            row = {
                "split": split,
                "image": image_path.name,
                "class_name": cls_name,
                "error_type": err_type,
                "pred_class": pred_class,
                "pred_score": pred_score,
                "best_iou": f"{best_iou:.4f}",
                "size_bin": bin_name,
                "box": " ".join(f"{v:.1f}" for v in target["box"]),
                **scene,
            }
            row["priority"] = priority_score(row)
            rows.append(row)
            per_image_rows[image_path].append(row)

        for pred in preds:
            if pred["idx"] in used_pred:
                continue
            if pred["score"] < conf:
                continue
            bin_name = size_bin(pred["box"], img_w, img_h)
            cls_name = names[pred["class_id"]]
            row = {
                "split": split,
                "image": image_path.name,
                "class_name": cls_name,
                "error_type": "FP",
                "pred_class": cls_name,
                "pred_score": f"{pred['score']:.4f}",
                "best_iou": "0.0000",
                "size_bin": bin_name,
                "box": " ".join(f"{v:.1f}" for v in pred["box"]),
                **scene,
            }
            row["priority"] = priority_score(row)
            rows.append(row)
            per_image_rows[image_path].append(row)

    out_dir.mkdir(parents=True, exist_ok=True)
    rows.sort(key=lambda r: int(r["priority"]), reverse=True)
    fieldnames = [
        "priority", "split", "image", "error_type", "class_name", "pred_class", "pred_score",
        "best_iou", "size_bin", "sceneType", "lighting", "weather", "quality", "angle", "source", "box"
    ]
    with open(out_dir / f"{split}_failures.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = Counter((r["class_name"], r["error_type"], r["size_bin"], r["sceneType"], r["angle"]) for r in rows)
    with open(out_dir / f"{split}_summary.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["class_name", "error_type", "size_bin", "sceneType", "angle", "count"])
        for key, count in summary.most_common():
            writer.writerow([*key, count])

    vis_count = 0
    for image_path, image_rows in sorted(per_image_rows.items(), key=lambda item: max(int(r["priority"]) for r in item[1]), reverse=True):
        if vis_count >= max_vis:
            break
        if not any(r["class_name"] in PRIORITY_CLASSES for r in image_rows):
            continue
        draw_failure(image_path, out_dir / "visuals" / split / image_path.name, image_rows)
        vis_count += 1

    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default="/mnt/sda1/yolov11/roadsideillegalvending4")
    parser.add_argument("--model", required=True)
    parser.add_argument("--splits", default="train,val,test")
    parser.add_argument("--out", required=True)
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--max-vis", type=int, default=80)
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    data_yaml = load_yaml(base_dir / "data" / "dataset.yaml")
    names = data_yaml["names"]
    model = YOLO(args.model)
    out_dir = Path(args.out)
    all_rows = []
    for split in [s.strip() for s in args.splits.split(",") if s.strip()]:
        all_rows.extend(mine_split(model, base_dir, split, names, out_dir, args.conf, args.iou, args.max_vis))

    with open(out_dir / "all_failures.csv", "w", newline="", encoding="utf-8-sig") as f:
        if all_rows:
            writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
            writer.writeheader()
            writer.writerows(all_rows)

    print(f"failure rows: {len(all_rows)}")
    print(f"output: {out_dir}")


if __name__ == "__main__":
    main()
