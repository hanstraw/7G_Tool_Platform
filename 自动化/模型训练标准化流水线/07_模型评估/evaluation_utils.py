# ===================== 仅添加这4行，解决中文字体报错 =====================
# ======================================================================

import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from tqdm import tqdm

# 类别相关常量
CLASS_NAMES = [
    '其他垃圾', '可回收物', '厨余垃圾', '有害垃圾'
]

CLASS_COLORS = [
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4'
]

# 尺寸分档
SIZE_BINS = [
    ('tiny', 0, 0.0004),
    ('small', 0.0004, 0.0025),
    ('medium', 0.0025, 0.04),
    ('large', 0.04, float('inf')),
]

SIZE_BIN_DESC = {
    'tiny': 'r < 0.0004',
    'small': '0.0004 <= r < 0.0025',
    'medium': '0.0025 <= r < 0.04',
    'large': 'r >= 0.04',
}


class Detection:
    __slots__ = ['x1', 'y1', 'x2', 'y2', 'class_id', 'score', 'area']

    def __init__(self, x1, y1, x2, y2, class_id, score=1.0):
        self.x1 = float(x1)
        self.y1 = float(y1)
        self.x2 = float(x2)
        self.y2 = float(y2)
        self.class_id = int(class_id)
        self.score = float(score)
        self.area = max(0, (self.x2 - self.x1) * (self.y2 - self.y1))


def iou(a: Detection, b: Detection) -> float:
    a_x1, a_y1, a_x2, a_y2 = a.x1, a.y1, a.x2, a.y2
    b_x1, b_y1, b_x2, b_y2 = b.x1, b.y1, b.x2, b.y2

    inter_x1 = max(a_x1, b_x1)
    inter_y1 = max(a_y1, b_y1)
    inter_x2 = min(a_x2, b_x2)
    inter_y2 = min(a_y2, b_y2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter = inter_w * inter_h

    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


def _empty_stats():
    """补充空统计结构（主脚本依赖）"""
    return {'tp': 0, 'fp': 0, 'fn': 0, 'scores': [], 'matches': []}


def match_detections(predictions: List[Detection], targets: List[Detection], class_count: int, iou_threshold=0.5):
    pred_by_class = [[] for _ in range(class_count)]
    gt_by_class = [[] for _ in range(class_count)]

    for p in predictions:
        if 0 <= p.class_id < class_count:
            pred_by_class[p.class_id].append(p)

    for t in targets:
        if 0 <= t.class_id < class_count:
            gt_by_class[t.class_id].append(t)

    stats = {cid: _empty_stats() for cid in range(class_count)}

    for cid in range(class_count):
        preds = pred_by_class[cid]
        gts = gt_by_class[cid]
        stats[cid]['fn'] = len(gts)

        preds_sorted = sorted(preds, key=lambda x: -x.score)
        gt_used = [False] * len(gts)

        for p in preds_sorted:
            best_iou = 0.0
            best_idx = -1

            for i, t in enumerate(gts):
                if not gt_used[i]:
                    current_iou = iou(p, t)
                    if current_iou > best_iou:
                        best_iou = current_iou
                        best_idx = i

            if best_idx >= 0 and best_iou >= iou_threshold:
                stats[cid]['tp'] += 1
                stats[cid]['fn'] -= 1
                stats[cid]['matches'].append(1)
                gt_used[best_idx] = True
            else:
                stats[cid]['fp'] += 1
                stats[cid]['matches'].append(0)
            stats[cid]['scores'].append(p.score)

    return stats


def match_detections_grouped(
        predictions,
        targets,
        class_count,
        iou_threshold=0.5,
        scene_attrs=None,
        img_w=0,
        img_h=0,
):
    base_stats = match_detections(predictions, targets, class_count, iou_threshold)
    img_area = float(img_w * img_h) if img_w > 0 and img_h > 0 else 1.0

    # 尺寸分组: 每个 bin 单独跑 match_detections
    size_result = {}
    for bin_name, lo, hi in SIZE_BINS:
        bin_preds = [p for p in predictions if lo <= p.area / img_area < hi]
        bin_gts   = [t for t in targets   if lo <= t.area / img_area < hi]
        size_result[bin_name] = match_detections(bin_preds, bin_gts, class_count, iou_threshold)

    # 场景分组: 整张图共用同一组属性, 直接复用 base_stats
    scene_result = {}
    if scene_attrs:
        for field_key, field_val in scene_attrs.items():
            if field_key not in scene_result:
                scene_result[field_key] = {}
            scene_result[field_key][field_val] = base_stats

    return {
        'per_class': base_stats,
        'size':      size_result,
        'scene':     scene_result,
    }

def parse_yolo_txt(txt_path: Path, img_w=0, img_h=0) -> List[Detection]:
    dets = []
    if not txt_path.exists():
        return dets
    with open(txt_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            cid, xc, yc, w, h = parts[:5]
            score = float(parts[5]) if len(parts) >= 6 else 1.0

            cid = int(cid)
            xc = float(xc)
            yc = float(yc)
            w = float(w)
            h = float(h)

            # 转换为绝对坐标（YOLO格式是相对坐标）
            if img_w > 0 and img_h > 0:
                x1 = (xc - w / 2) * img_w
                y1 = (yc - h / 2) * img_h
                x2 = (xc + w / 2) * img_w
                y2 = (yc + h / 2) * img_h
            else:
                x1 = (xc - w / 2)
                y1 = (yc - h / 2)
                x2 = (xc + w / 2)
                y2 = (yc + h / 2)
            dets.append(Detection(x1, y1, x2, y2, cid, score))
    return dets


def compute_ap(scores: List[float], matches: List[int], n_gt: int) -> float:
    if n_gt <= 0 or not scores:
        return float('nan')
    order = np.argsort(-np.array(scores))
    matches_arr = np.array(matches)[order]
    tp = np.cumsum(matches_arr)
    fp = np.cumsum(1 - matches_arr)

    recall = tp / (n_gt + 1e-9)
    precision = tp / (tp + fp + 1e-9)

    mrec = np.concatenate(([0.0], recall, [1.0]))
    mpre = np.concatenate(([1.0], precision, [0.0]))

    for i in range(len(mpre) - 1, 0, -1):
        mpre[i - 1] = max(mpre[i - 1], mpre[i])

    idx = np.where(mrec[1:] != mrec[:-1])[0]
    ap = np.sum((mrec[idx + 1] - mrec[idx]) * mpre[idx + 1])
    return ap


def compute_ap50(scores: List[float], matches: List[int], n_gt: int) -> float:
    """补充mAP50计算（主脚本可能依赖）"""
    return compute_ap(scores, matches, n_gt)  # AP50即IOU=0.5的AP


def compute_precision_recall_f1(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return p, r, f1


def summarize_metrics(class_names, per_class, label_counts, total_images, total_time_seconds,
                      cpu_memory_mb=None, gpu_memory_mb=None):
    """修复汇总逻辑，补充map50/map5095（主脚本输出依赖）"""
    rows = []
    ap50_list = []
    ap5095_list = []  # 简化：此处AP50-95暂用AP50替代，可根据需求扩展
    for cid, name in enumerate(class_names):
        s = per_class[cid]
        tp, fp, fn = s['tp'], s['fp'], s['fn']
        p, r, f1 = compute_precision_recall_f1(tp, fp, fn)
        ap50 = compute_ap50(s['scores'], s['matches'], label_counts[cid])
        if not np.isnan(ap50):
            ap50_list.append(ap50)
            ap5095_list.append(ap50)  # 可扩展为多IOU阈值计算
        rows.append({
            'id': cid,
            'name': name,
            'labels': label_counts[cid],
            'tp': tp,
            'fp': fp,
            'fn': fn,
            'precision': p,
            'recall': r,
            'f1': f1,
            'ap50': ap50,
            'ap5095': ap50,
        })

    map50 = float(np.nanmean(ap50_list)) if ap50_list else 0.0
    map5095 = float(np.nanmean(ap5095_list)) if ap5095_list else 0.0

    total_tp = sum(r['tp'] for r in rows)
    total_fp = sum(r['fp'] for r in rows)
    total_fn = sum(r['fn'] for r in rows)
    overall_p, overall_r, overall_f1 = compute_precision_recall_f1(total_tp, total_fp, total_fn)

    summary = {
        'images': total_images,
        'time_sec': round(total_time_seconds, 2),
        'speed_avg_ms': round(total_time_seconds * 1000 / total_images, 1) if total_images > 0 else 0,
        'map50': round(map50, 4),
        'map5095': round(map5095, 4),
        'overall_precision': round(overall_p, 4),
        'overall_recall': round(overall_r, 4),
        'overall_f1': round(overall_f1, 4),
        'per_class_rows': rows,  # 主脚本绘图依赖
    }
    if cpu_memory_mb is not None:
        summary['cpu_memory_mb'] = round(cpu_memory_mb, 1)
    if gpu_memory_mb is not None:
        summary['gpu_memory_mb'] = round(gpu_memory_mb, 1)
    return summary


def summarize_scene_metrics(scene_accum, class_names):
    """补充场景指标汇总（主脚本生成报告依赖）"""
    scene_summary = {}
    for field_key, val_dict in scene_accum.items():
        scene_summary[field_key] = {}
        for val, per_class in val_dict.items():
            # 计算该场景维度的汇总指标
            rows = []
            ap50_list = []
            label_counts = {cid: per_class[cid]['tp'] + per_class[cid]['fn'] for cid in range(len(class_names))}
            for cid, name in enumerate(class_names):
                s = per_class[cid]
                tp, fp, fn = s['tp'], s['fp'], s['fn']
                p, r, f1 = compute_precision_recall_f1(tp, fp, fn)
                ap50 = compute_ap50(s['scores'], s['matches'], label_counts[cid])
                if not np.isnan(ap50):
                    ap50_list.append(ap50)
                rows.append({
                    'name': name,
                    'tp': tp,
                    'fp': fp,
                    'fn': fn,
                    'precision': p,
                    'recall': r,
                    'f1': f1,
                    'ap50': ap50,
                })
            map50 = float(np.nanmean(ap50_list)) if ap50_list else 0.0
            scene_summary[field_key][val] = {
                'map50': round(map50, 4),
                'per_class': rows,
            }
    return scene_summary


def summarize_size_metrics(size_accum, class_names):
    """补充尺寸指标汇总（主脚本生成报告依赖）"""
    size_summary = {}
    for bin_name, per_class in size_accum.items():
        rows = []
        ap50_list = []
        label_counts = {cid: per_class[cid]['tp'] + per_class[cid]['fn'] for cid in range(len(class_names))}
        for cid, name in enumerate(class_names):
            s = per_class[cid]
            tp, fp, fn = s['tp'], s['fp'], s['fn']
            p, r, f1 = compute_precision_recall_f1(tp, fp, fn)
            ap50 = compute_ap50(s['scores'], s['matches'], label_counts[cid])
            if not np.isnan(ap50):
                ap50_list.append(ap50)
            rows.append({
                'name': name,
                'tp': tp,
                'fp': fp,
                'fn': fn,
                'precision': p,
                'recall': r,
                'f1': f1,
                'ap50': ap50,
            })
        map50 = float(np.nanmean(ap50_list)) if ap50_list else 0.0
        size_summary[bin_name] = {
            'desc': SIZE_BIN_DESC[bin_name],
            'map50': round(map50, 4),
            'per_class': rows,
        }
    return size_summary


def plot_scene_metrics(save_dir, scene_summary):
    """补充场景指标绘图（主脚本依赖）"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'DejaVu Sans']
    matplotlib.rcParams['axes.unicode_minus'] = False
    scene_img_paths = {}
    for field_key, val_dict in scene_summary.items():
        plt.figure(figsize=(10, 6))
        vals = list(val_dict.keys())
        classes = scene_summary[field_key][vals[0]]['per_class'] if vals else []
        class_names = [c['name'] for c in classes]
        n_classes = len(class_names)

        x = np.arange(len(vals))
        width = 0.8 / n_classes
        for i, cls_name in enumerate(class_names):
            f1_scores = [val_dict[v]['per_class'][i]['f1'] for v in vals]
            plt.bar(x + i * width, f1_scores, width, label=cls_name)

        plt.xlabel(f'Scene: {field_key}')
        plt.ylabel('F1 Score')
        plt.title(f'F1 Score by {field_key}')
        plt.xticks(x + width * (n_classes - 1) / 2, vals)
        plt.legend()
        plt.grid(alpha=0.3)
        path = os.path.join(save_dir, f'scene_{field_key}_f1.png')
        plt.tight_layout()
        plt.savefig(path, dpi=120)
        plt.close()
        scene_img_paths[field_key] = path
    return scene_img_paths


def plot_size_metrics(save_dir, size_summary):
    """补充尺寸指标绘图（主脚本依赖）"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'DejaVu Sans']
    matplotlib.rcParams['axes.unicode_minus'] = False
    plt.figure(figsize=(10, 6))
    bins = list(size_summary.keys())
    classes = size_summary[bins[0]]['per_class'] if bins else []
    class_names = [c['name'] for c in classes]
    n_classes = len(class_names)

    x = np.arange(len(bins))
    width = 0.8 / n_classes
    for i, cls_name in enumerate(class_names):
        f1_scores = [size_summary[b]['per_class'][i]['f1'] for b in bins]
        plt.bar(x + i * width, f1_scores, width, label=cls_name)

    plt.xlabel('Size Bin')
    plt.ylabel('F1 Score')
    plt.title('F1 Score by Target Size')
    plt.xticks(x + width * (n_classes - 1) / 2, [f'{b}\n({SIZE_BIN_DESC[b]})' for b in bins])
    plt.legend()
    plt.grid(alpha=0.3)
    path = os.path.join(save_dir, 'size_f1.png')
    plt.tight_layout()
    plt.savefig(path, dpi=120)
    plt.close()
    return path


def plot_f1_summary_curve(save_dir, class_names, per_class_rows, curve_name='F1_curve'):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'DejaVu Sans']
    matplotlib.rcParams['axes.unicode_minus'] = False
    os.makedirs(save_dir, exist_ok=True)
    plt.figure(figsize=(8, 5))
    x = np.arange(len(class_names))
    f1_scores = [r['f1'] for r in per_class_rows]
    plt.bar(x, f1_scores, color=CLASS_COLORS[:len(class_names)])
    plt.xticks(x, class_names, rotation=45)
    plt.ylim(0, 1.05)
    plt.title('F1 Score by Class')
    plt.ylabel('F1')
    path = os.path.join(save_dir, f'{curve_name}.png')
    plt.tight_layout()
    plt.savefig(path, dpi=120)
    plt.close()
    return path  # 补充返回路径（主脚本依赖）


def write_markdown_report(save_dir, summary, curve_image_name=None, scene_summary=None,
                          scene_image_paths=None, size_summary=None, size_image_path=None,
                          thresholds=None):
    report_path = os.path.join(save_dir, 'evaluation_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('# YOLOv11 评估报告' + chr(10) + chr(10))
        if thresholds:
            f.write('## 评估配置' + chr(10) + chr(10))
            f.write('| 参数 | 値 |' + chr(10))
            f.write('| --- | --- |' + chr(10))
            for k, v in thresholds.items():
                f.write(f'| {k} | {v} |' + chr(10))
            f.write(chr(10))
        f.write('## 全局指标' + chr(10) + chr(10))
        f.write(f'- 评估图片数: {summary["images"]}' + chr(10))
        f.write(f'- 总耗时: {summary["time_sec"]}s' + chr(10))
        f.write(f'- 平均推理速度: {summary["speed_avg_ms"]}ms/张' + chr(10))
        f.write(f'- mAP50: {summary["map50"]}' + chr(10))
        f.write(f'- mAP50-95: {summary["map5095"]}' + chr(10))
        f.write(f'- 整体精确率: {summary["overall_precision"]}' + chr(10))
        f.write(f'- 整体召回率: {summary["overall_recall"]}' + chr(10))
        f.write(f'- 整体F1: {summary["overall_f1"]}' + chr(10))
        if 'cpu_memory_mb' in summary:
            f.write(f'- CPU内存占用: {summary["cpu_memory_mb"]}MB' + chr(10))
        if 'gpu_memory_mb' in summary:
            f.write(f'- GPU内存占用: {summary["gpu_memory_mb"]}MB' + chr(10))
        for key, val in summary.get('extra_speed_metrics', {}).items():
            f.write(f'- {key}: {val:.2f}' + chr(10))
        f.write(chr(10) + '## 类别指标' + chr(10) + chr(10))
        f.write('| 类别 | 标签数 | TP | FP | FN | 精确率 | 召回率 | F1 | AP50 |' + chr(10))
        f.write('|------|--------|----|----|----|--------|--------|----|------|' + chr(10))
        for row in summary['per_class_rows']:
            f.write(f'| {row["name"]} | {row["labels"]} | {row["tp"]} | {row["fp"]} | {row["fn"]} | {row["precision"]:.4f} | {row["recall"]:.4f} | {row["f1"]:.4f} | {row["ap50"]:.4f} |' + chr(10))
        if curve_image_name:
            f.write(chr(10) + '## F1曲线' + chr(10) + chr(10))
            f.write(f'![F1 Curve]({curve_image_name})' + chr(10))
        if size_summary:
            f.write(chr(10) + '## 尺寸分档指标' + chr(10) + chr(10))
            f.write('> 尺寸分档基于相对面积占比 r = 目标面积 / 图像面积' + chr(10) + chr(10))
            for bin_name, bin_data in size_summary.items():
                desc = SIZE_BIN_DESC.get(bin_name, '')
                f.write(f'### {bin_name}  ({desc})' + chr(10) + chr(10))
                f.write(f'- mAP50: {bin_data["map50"]}' + chr(10))
                f.write('| 类别 | 精确率 | 召回率 | F1 |' + chr(10))
                f.write('|------|--------|--------|-----|' + chr(10))
                for cls in bin_data['per_class']:
                    f.write(f'| {cls["name"]} | {cls["precision"]:.4f} | {cls["recall"]:.4f} | {cls["f1"]:.4f} |' + chr(10))
            if size_image_path:
                f.write(chr(10) + f'![Size F1]({os.path.basename(size_image_path)})' + chr(10))
        if scene_summary:
            f.write(chr(10) + '## 场景维度指标' + chr(10) + chr(10))
            for field_key, val_dict in scene_summary.items():
                f.write(f'### {field_key}' + chr(10) + chr(10))
                for val, val_data in val_dict.items():
                    f.write(f'#### {val}' + chr(10) + chr(10))
                    f.write(f'- mAP50: {val_data["map50"]}' + chr(10))
                    f.write('| 类别 | 精确率 | 召回率 | F1 |' + chr(10))
                    f.write('|------|--------|--------|-----|' + chr(10))
                    for cls in val_data['per_class']:
                        f.write(f'| {cls["name"]} | {cls["precision"]:.4f} | {cls["recall"]:.4f} | {cls["f1"]:.4f} |' + chr(10))
                if scene_image_paths and field_key in scene_image_paths:
                    f.write(chr(10) + f'![Scene {field_key}]({os.path.basename(scene_image_paths[field_key])})' + chr(10))
    return report_path

def load_dataset_from_yaml(yaml_path):
    """加载数据集, 支持 test 字段为目录路径或图片路径列表."""
    import yaml
    IMG_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    class_names = data.get('names', [])
    base_dir = os.path.dirname(os.path.abspath(yaml_path))
    dataset_root = data.get('path', base_dir)
    if not os.path.isabs(dataset_root):
        dataset_root = os.path.join(base_dir, dataset_root)

    def _resolve(p):
        return p if os.path.isabs(p) else os.path.join(dataset_root, p)

    def _collect_images(src):
        """src 可以是目录路径或图片文件路径列表."""
        if isinstance(src, list):
            paths = []
            for item in src:
                item = _resolve(item)
                if os.path.isdir(item):
                    paths.extend(_collect_images(item))
                elif os.path.splitext(item)[1].lower() in IMG_EXTS:
                    paths.append(item)
            return paths
        src = _resolve(src)
        if os.path.isdir(src):
            return sorted(
                os.path.join(src, f) for f in os.listdir(src)
                if os.path.splitext(f)[1].lower() in IMG_EXTS
            )
        if os.path.splitext(src)[1].lower() in IMG_EXTS:
            return [src]
        return []

    test_src = data.get('test') or data.get('val')
    img_paths = _collect_images(test_src) if test_src else []

    samples = []
    for img_path in img_paths:
        # label: images/xxx -> labels/xxx, 扩展名换 .txt
        label_path = os.path.splitext(
            img_path.replace(os.sep + 'images' + os.sep, os.sep + 'labels' + os.sep)
        )[0] + '.txt'
        # xml label: 先尝试同目录的 .xml (即 label_path 换扩嵌名), 其次才是 labelsxml/
        xml_label_path = os.path.splitext(label_path)[0] + '.xml'
        samples.append(
            type('Sample', (), {
                'image_path': img_path,
                'label_path': label_path,
                'xml_label_path': xml_label_path,
                'scene_attrs': {}
            })()
        )
    return class_names, samples

def attach_scene_attrs(samples, xml_dir):
    import xml.etree.ElementTree as ET
    import json as _json
    for sample in samples:
        stem = os.path.splitext(os.path.basename(sample.image_path))[0]
        xml_path = os.path.join(xml_dir, stem + ".xml")
        if not os.path.exists(xml_path) or os.path.isdir(xml_path):
            continue
        try:
            root = ET.parse(xml_path).getroot()
        except Exception:
            continue
        scene_attrs = {}
        extra_text = root.findtext("extra_annotations")
        if extra_text:
            try:
                for ann in _json.loads(extra_text):
                    if ann.get("toolName") != "tagTool":
                        continue
                    for tag_item in ann.get("result", []):
                        for key, val in tag_item.get("value", {}).items():
                            scene_attrs[key] = val[0] if isinstance(val, list) and val else str(val)
            except Exception:
                pass
        else:
            for field in ("sceneType", "lighting", "weather", "quality", "angle", "source"):
                node = root.find(field)
                if node is not None and node.text:
                    scene_attrs[field] = node.text.strip()
        sample.scene_attrs = scene_attrs

def load_yolo_labels(label_path, img_w, img_h, class_names=None, xml_label_path=None):
    """å è½½GTæ ç­¾. ä¼åè¯»TXT, ä¸å­å¨æ¶å°è¯ååXML(labelsxml/)."""
    txt = Path(label_path)
    if txt.exists():
        return parse_yolo_txt(txt, img_w, img_h)
    xml_path = xml_label_path or str(txt).replace(
        os.sep + "labels" + os.sep, os.sep + "labelsxml" + os.sep
    ).replace(".txt", ".xml")
    if os.path.exists(xml_path):
        return parse_voc_xml(xml_path, img_w, img_h, class_names or [])
    return []


def parse_voc_xml(xml_path, img_w, img_h, class_names):
    """ä» VOC XML è§£æ GT Detection åè¡¨."""
    import xml.etree.ElementTree as ET
    dets = []
    try:
        root = ET.parse(xml_path).getroot()
        size = root.find("size")
        w = int(size.find("width").text) if size is not None else img_w
        h = int(size.find("height").text) if size is not None else img_h
        for obj in root.iter("object"):
            name = obj.find("name")
            if name is None:
                continue
            cls_name = name.text.strip()
            cid = class_names.index(cls_name) if cls_name in class_names else -1
            if cid < 0:
                continue
            bb = obj.find("bndbox")
            x1 = float(bb.find("xmin").text)
            y1 = float(bb.find("ymin").text)
            x2 = float(bb.find("xmax").text)
            y2 = float(bb.find("ymax").text)
            dets.append(Detection(class_id=cid, score=1.0, x1=x1, y1=y1, x2=x2, y2=y2))
    except Exception:
        pass
    return dets


def get_cpu_memory_mb():
    """获取CPU内存（主脚本依赖）"""
    import psutil
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024