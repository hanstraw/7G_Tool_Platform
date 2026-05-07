"""
YOLOv11 批量预标注 -> LabelU JSON

用法:
    python pre_annotate.py \
        --model  ../modelTrain/weights/best.pt \
        --images E:/071garbage/media/images \
        --output ./pre_annotate_result.json \
        --base-url /api/v1/tasks/attachment/upload/1 \
        --conf 0.35 --iou 0.5 \
        --sceneType urbanArterial \
        --lighting normalDaylight \
        --weather sunny \
        --quality clear \
        --angle eyeLevel \
        --source cameraCapture

全量属性可选值:
  sceneType : backAlley | commercialStreet | constructionSite | parkSquare |
              residentialRoad | schoolArea | urbanArterial | urbanVillage
  lighting  : backlight | dusk | heavyShadow | nightNoLight | nightWithLight |
              normalDaylight | strongDaylight | weakDaylight
  weather   : cloudy | dust | foggy | heavyRain | lightRain | snowy | sunny
  quality   : clear | motionBlur | occluded | overexposed | severeBlurry |
              slightBlurry | underexposed
  angle     : aerialView | eyeLevel | lowAngle | obliqueView | topView
  source    : cameraCapture | manualShoot | syntheticData | webCollect
"""

import argparse
import json
import os
import uuid

from tqdm import tqdm

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# ── 全量属性枚举 ──────────────────────────────────────────────
SCENE_OPTIONS = {
    "sceneType": ["backAlley", "commercialStreet", "constructionSite", "parkSquare",
                  "residentialRoad", "schoolArea", "urbanArterial", "urbanVillage"],
    "lighting":  ["backlight", "dusk", "heavyShadow", "nightNoLight", "nightWithLight",
                  "normalDaylight", "strongDaylight", "weakDaylight"],
    "weather":   ["cloudy", "dust", "foggy", "heavyRain", "lightRain", "snowy", "sunny"],
    "quality":   ["clear", "motionBlur", "occluded", "overexposed", "severeBlurry",
                  "slightBlurry", "underexposed"],
    "angle":     ["aerialView", "eyeLevel", "lowAngle", "obliqueView", "topView"],
    "source":    ["cameraCapture", "manualShoot", "syntheticData", "webCollect"],
}

SCENE_LABELS = {
    "sceneType": "场景类型",
    "lighting":  "光照条件",
    "weather":   "天气",
    "quality":   "图像质量",
    "angle":     "拍摄角度",
    "source":    "数据来源",
}


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _build_tag_annotations(scene_attrs: dict) -> dict:
    """构建 labelU tagTool annotation block."""
    results = []
    for key, val in scene_attrs.items():
        if val:
            results.append({
                "id": _uid(),
                "type": "tag",
                "value": {key: [val]},
            })
    return {"toolName": "tagTool", "result": results}


def _build_rect_annotations(boxes) -> dict:
    """
    boxes: list of (x, y, w, h, label, conf)  — absolute pixel coords, x/y = top-left
    """
    results = []
    for order, (x, y, w, h, label, conf) in enumerate(boxes, start=1):
        results.append({
            "id": _uid(),
            "x": round(x, 4),
            "y": round(y, 4),
            "width": round(w, 4),
            "height": round(h, 4),
            "label": label,
            "order": order,
            "attributes": {"conf": round(float(conf), 4)},
        })
    return {"toolName": "rectTool", "result": results}


def run(args):
    # ── 加载模型 ──────────────────────────────────────────────
    try:
        from ultralytics import YOLO
    except ImportError:
        raise SystemExit("请先安装 ultralytics: pip install ultralytics")

    model = YOLO(args.model)

    # ── 收集图片 ──────────────────────────────────────────────
    img_dir = args.images
    image_files = sorted(
        f for f in os.listdir(img_dir)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTS
    )
    if not image_files:
        raise SystemExit(f"未找到图片: {img_dir}")
    print(f"找到图片: {len(image_files)}")

    # ── 场景属性(整批统一) ────────────────────────────────────
    scene_attrs = {
        "sceneType": args.sceneType,
        "lighting":  args.lighting,
        "weather":   args.weather,
        "quality":   args.quality,
        "angle":     args.angle,
        "source":    args.source,
    }
    print("\n本批场景属性:")
    for k, v in scene_attrs.items():
        print(f"  {SCENE_LABELS[k]}({k}): {v or '(未设置)'}")
    print()

    tag_ann = _build_tag_annotations(scene_attrs)

    # ── 批量推理 ──────────────────────────────────────────────
    records = []
    for idx, fname in enumerate(tqdm(image_files, desc="推理中"), start=1):
        img_path = os.path.join(img_dir, fname)
        results = model.predict(
            img_path,
            conf=args.conf,
            iou=args.iou,
            verbose=False,
        )
        r = results[0]
        img_h, img_w = r.orig_shape[:2]

        boxes = []
        for box in r.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            label = model.names[int(box.cls[0])]
            conf = float(box.conf[0])
            boxes.append((x1, y1, x2 - x1, y2 - y1, label, conf))

        result_obj = {
            "width": img_w,
            "height": img_h,
            "rotate": 0,
            "annotations": [
                tag_ann,
                _build_rect_annotations(boxes),
                {"toolName": "textTool", "result": []},
            ],
        }

        records.append({
            "id": idx,
            "result": json.dumps(result_obj, ensure_ascii=False),
            "folder": img_dir,
            "url": f"{args.base_url}/{fname}",
            "fileName": fname,
        })

    # ── 输出 JSON ─────────────────────────────────────────────
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    total_boxes = sum(
        len(json.loads(rec["result"])["annotations"][1]["result"])
        for rec in records
    )
    print(f"\n完成: {len(records)} 张图片, 共 {total_boxes} 个预标注框")
    print(f"输出: {args.output}")


# ── CLI ───────────────────────────────────────────────────────

def _add_scene_args(p: argparse.ArgumentParser):
    for key, options in SCENE_OPTIONS.items():
        p.add_argument(
            f"--{key}",
            choices=options,
            default=None,
            metavar="|".join(options),
            help=f"{SCENE_LABELS[key]} (可选值: {', '.join(options)})",
        )


def main():
    p = argparse.ArgumentParser(
        description="YOLOv11 批量预标注 -> LabelU JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--model",    required=True, help="YOLOv11 .pt 权重路径")
    p.add_argument("--images",   required=True, help="图片目录")
    p.add_argument("--output",   default="./pre_annotate_result.json", help="输出 JSON 路径")
    p.add_argument("--base-url", default="/api/v1/tasks/attachment/upload/1", dest="base_url")
    p.add_argument("--conf",     type=float, default=0.35, help="置信度阈值")
    p.add_argument("--iou",      type=float, default=0.5,  help="NMS IoU 阈值")
    _add_scene_args(p)
    args = p.parse_args()
    run(args)


if __name__ == "__main__":
    main()
