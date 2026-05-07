import os
import time

import cv2
import numpy as np
import onnxruntime

from evaluation_utils import (
    CLASS_NAMES,
    Detection,
    SIZE_BINS,
    _empty_stats,
    attach_scene_attrs,
    get_cpu_memory_mb,
    load_dataset_from_yaml,
    load_yolo_labels,
    match_detections_grouped,
    plot_f1_summary_curve,
    plot_scene_metrics,
    plot_size_metrics,
    summarize_metrics,
    summarize_scene_metrics,
    summarize_size_metrics,
    write_markdown_report,
)

INPUT_IMG_H  = 640
INPUT_IMG_W  = 640
NMS_THRESH   = 0.45
OBJECT_THRESH = 0.35
MODEL_PATH   = "./modelTrain/onnx/best_0317.onnx"
DATA_PATH    = "./data/test.yaml"
XML_DIR      = ""          # VOC XML 目录, 留空则跳过场景分组
SAVE_DIR     = "./modelEvaluation/results_onnx"
os.makedirs(SAVE_DIR, exist_ok=True)


class DetectBox:
    def __init__(self, class_id, score, xmin, ymin, xmax, ymax):
        self.class_id = class_id
        self.score = score
        self.xmin = xmin
        self.ymin = ymin
        self.xmax = xmax
        self.ymax = ymax


def iou_xyxy(box1, box2):
    xmin = max(box1[0], box2[0])
    ymin = max(box1[1], box2[1])
    xmax = min(box1[2], box2[2])
    ymax = min(box1[3], box2[3])
    inner_w = max(0.0, xmax - xmin)
    inner_h = max(0.0, ymax - ymin)
    inner_area = inner_w * inner_h
    area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])
    return inner_area / (area1 + area2 - inner_area + 1e-9)


def nms(detect_result):
    pred_boxes = []
    sorted_boxes = sorted(detect_result, key=lambda x: x.score, reverse=True)
    for i in range(len(sorted_boxes)):
        current = sorted_boxes[i]
        if current.class_id == -1:
            continue
        pred_boxes.append(current)
        for j in range(i + 1, len(sorted_boxes)):
            other = sorted_boxes[j]
            if current.class_id != other.class_id or other.class_id == -1:
                continue
            if iou_xyxy(
                (current.xmin, current.ymin, current.xmax, current.ymax),
                (other.xmin, other.ymin, other.xmax, other.ymax),
            ) > NMS_THRESH:
                other.class_id = -1
    return pred_boxes


def preprocess_image(img_src, resize_w, resize_h):
    image = cv2.resize(img_src, (resize_w, resize_h), interpolation=cv2.INTER_LINEAR)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = image.astype(np.float32) / 255.0
    image = image.transpose((2, 0, 1))
    return np.expand_dims(image, axis=0)


def postprocess_yolo_onnx(out, img_h, img_w, class_num):
    out = out[0]
    bbox = out[:, 0:4]
    cls_scores = out[:, 4:4 + class_num]
    scale_h = img_h / INPUT_IMG_H
    scale_w = img_w / INPUT_IMG_W
    detect_result = []
    for i in range(out.shape[0]):
        scores = cls_scores[i]
        class_id = int(np.argmax(scores))
        score = float(scores[class_id])
        if score < OBJECT_THRESH:
            continue
        cx, cy, w, h = bbox[i]
        x1 = max(0.0, (cx - w / 2.0) * scale_w)
        y1 = max(0.0, (cy - h / 2.0) * scale_h)
        x2 = min(float(img_w), (cx + w / 2.0) * scale_w)
        y2 = min(float(img_h), (cy + h / 2.0) * scale_h)
        detect_result.append(DetectBox(class_id, score, x1, y1, x2, y2))
    return nms(detect_result)


def main():
    print("开始 ONNX 评估 (支持场景/尺寸分组)")
    class_names, samples = load_dataset_from_yaml(DATA_PATH)
    class_count = len(class_names)

    if XML_DIR and os.path.isdir(XML_DIR):
        attach_scene_attrs(samples, XML_DIR)
        print(f"已加载场景属性: {XML_DIR}")

    available = onnxruntime.get_available_providers()
    providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if 'CUDAExecutionProvider' in available else ['CPUExecutionProvider']
    session = onnxruntime.InferenceSession(MODEL_PATH, providers=providers)
    input_name = session.get_inputs()[0].name

    # 累加器
    global_per_class = {cid: _empty_stats() for cid in range(class_count)}
    scene_accum: dict = {}
    size_accum = {b[0]: {cid: _empty_stats() for cid in range(class_count)} for b in SIZE_BINS}
    label_counts = np.zeros(class_count, dtype=int)
    inference_seconds = 0.0

    start_time = time.perf_counter()

    for sample in samples:
        image = cv2.imread(sample.image_path)
        if image is None:
            continue
        img_h, img_w = image.shape[:2]

        gt_boxes = load_yolo_labels(sample.label_path, img_w, img_h,
                                    class_names=class_names,
                                    xml_label_path=getattr(sample, 'xml_label_path', None))
        for gt in gt_boxes:
            if 0 <= gt.class_id < class_count:
                label_counts[gt.class_id] += 1

        input_tensor = preprocess_image(image, INPUT_IMG_W, INPUT_IMG_H)
        t0 = time.perf_counter()
        outputs = session.run(None, {input_name: input_tensor})
        inference_seconds += time.perf_counter() - t0

        pred_boxes = postprocess_yolo_onnx(outputs[0], img_h, img_w, class_count)
        predictions = [
            Detection(b.xmin, b.ymin, b.xmax, b.ymax, b.class_id, b.score)
            for b in pred_boxes
        ]

        grouped = match_detections_grouped(
            predictions, gt_boxes, class_count,
            iou_threshold=0.5,
            scene_attrs=sample.scene_attrs if sample.scene_attrs else None,
            img_w=img_w, img_h=img_h,
        )

        # 合并全局
        for cid in range(class_count):
            for k in ('tp', 'fp', 'fn'):
                global_per_class[cid][k] += grouped['per_class'][cid][k]
            global_per_class[cid]['scores'].extend(grouped['per_class'][cid]['scores'])
            global_per_class[cid]['matches'].extend(grouped['per_class'][cid]['matches'])

        # 合并场景
        for field_key, val_dict in grouped['scene'].items():
            if field_key not in scene_accum:
                scene_accum[field_key] = {}
            for val, pc in val_dict.items():
                if val not in scene_accum[field_key]:
                    scene_accum[field_key][val] = {cid: _empty_stats() for cid in range(class_count)}
                for cid in range(class_count):
                    for k in ('tp', 'fp', 'fn'):
                        scene_accum[field_key][val][cid][k] += pc[cid][k]
                    scene_accum[field_key][val][cid]['scores'].extend(pc[cid]['scores'])
                    scene_accum[field_key][val][cid]['matches'].extend(pc[cid]['matches'])

        # 合并尺寸
        for bin_name, pc in grouped['size'].items():
            for cid in range(class_count):
                for k in ('tp', 'fp', 'fn'):
                    size_accum[bin_name][cid][k] += pc[cid][k]
                size_accum[bin_name][cid]['scores'].extend(pc[cid]['scores'])
                size_accum[bin_name][cid]['matches'].extend(pc[cid]['matches'])

    total_time = time.perf_counter() - start_time
    cpu_mb = get_cpu_memory_mb()

    summary = summarize_metrics(
        class_names=class_names,
        per_class=global_per_class,
        label_counts=label_counts,
        total_images=len(samples),
        total_time_seconds=total_time,
        cpu_memory_mb=cpu_mb,
        gpu_memory_mb=None,
    )
    summary['extra_speed_metrics'] = {
        '平均推理耗时(ms/图)': (inference_seconds / max(len(samples), 1)) * 1000,
    }

    scene_summary = summarize_scene_metrics(scene_accum, class_names) if scene_accum else {}
    size_summary  = summarize_size_metrics(size_accum, class_names)

    curve_path      = plot_f1_summary_curve(SAVE_DIR, class_names, summary['per_class_rows'])
    scene_img_paths = plot_scene_metrics(SAVE_DIR, scene_summary) if scene_summary else {}
    size_img_path   = plot_size_metrics(SAVE_DIR, size_summary)

    report_path = write_markdown_report(
        SAVE_DIR, summary,
        curve_image_name=os.path.basename(curve_path),
        scene_summary=scene_summary,
        scene_image_paths=scene_img_paths,
        size_summary=size_summary,
        size_image_path=size_img_path,
        thresholds={
            '模型路径':     MODEL_PATH,
            '数据集':       DATA_PATH,
            '输入尺寸':     f'{INPUT_IMG_W}x{INPUT_IMG_H}',
            '置信度阈值':   OBJECT_THRESH,
            'NMS IoU 阈值': NMS_THRESH,
            '推理后端':     'ONNX Runtime',
        },
    )

    print(f"图片: {len(samples)} | mAP50: {summary['map50']:.4f}")
    print(f"报告: {report_path}")


if __name__ == '__main__':
    main()
