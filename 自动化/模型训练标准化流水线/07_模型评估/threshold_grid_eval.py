import argparse
import csv
import os
import sys
from pathlib import Path


def parse_report(path):
    metrics = {}
    rows = {}
    in_class_table = False
    in_global_section = False
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## 全局指标"):
                in_global_section = True
            elif line.startswith("## ") and not line.startswith("## 全局指标"):
                in_global_section = False
            elif in_global_section and line.startswith("- mAP50:"):
                metrics["mAP50"] = float(line.split(":", 1)[1].strip())
            elif in_global_section and line.startswith("- 整体精确率:"):
                metrics["precision"] = float(line.split(":", 1)[1].strip())
            elif in_global_section and line.startswith("- 整体召回率:"):
                metrics["recall"] = float(line.split(":", 1)[1].strip())
            elif in_global_section and line.startswith("- 整体F1:"):
                metrics["f1"] = float(line.split(":", 1)[1].strip())
            elif line.startswith("| 类别 | 标签数"):
                in_class_table = True
            elif in_class_table and line.startswith("|") and not line.startswith("|---"):
                parts = [p.strip() for p in line.strip("|").split("|")]
                if len(parts) == 9 and parts[0] != "类别":
                    rows[parts[0]] = {
                        "precision": float(parts[5]),
                        "recall": float(parts[6]),
                        "f1": float(parts[7]),
                        "ap50": float(parts[8]),
                    }
            elif in_class_table and line.startswith("## F1"):
                in_class_table = False
    return metrics, rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default="/mnt/sda1/yolov11/roadsideillegalvending4")
    parser.add_argument("--model", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--xml-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--confs", default="0.20,0.25,0.30,0.35,0.40")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(args.base_dir) / "scripts"))
    if not args.summary_only:
        import cloud_based_evaluation

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_rows = []
    for conf in [float(v) for v in args.confs.split(",")]:
        run_dir = out_dir / f"conf_{conf:.2f}"
        if not args.summary_only:
            cloud_based_evaluation.CONF_THRES = conf
            cloud_based_evaluation.IOU_THRES = 0.5
            cloud_based_evaluation.IMGSZ = 1280
            cloud_based_evaluation.main(
                model_path=args.model,
                data_path=args.data,
                xml_dir=args.xml_dir,
                save_dir=str(run_dir),
            )
        metrics, classes = parse_report(run_dir / "evaluation_report.md")
        row = {
            "conf": f"{conf:.2f}",
            **metrics,
            "streetVendor_other_f1": classes.get("streetVendor_other", {}).get("f1", 0.0),
            "streetVendor_other_recall": classes.get("streetVendor_other", {}).get("recall", 0.0),
            "streetVendor_other_precision": classes.get("streetVendor_other", {}).get("precision", 0.0),
            "streetVendor_vegetablet_f1": classes.get("streetVendor_vegetablet", {}).get("f1", 0.0),
            "object_basket_f1": classes.get("object_basket", {}).get("f1", 0.0),
            "report": str(run_dir / "evaluation_report.md"),
        }
        summary_rows.append(row)

    with open(out_dir / "threshold_grid_summary.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    print(out_dir / "threshold_grid_summary.csv")


if __name__ == "__main__":
    main()
