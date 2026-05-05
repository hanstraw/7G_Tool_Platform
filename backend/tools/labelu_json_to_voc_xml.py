"""
仅执行 LabelU JSON -> VOC XML 的转换脚本（平台内置版）。

说明：
1) 该脚本是 7G_Tool_Platform 内部副本，不依赖外部项目目录。
2) 建议通过平台传参运行：
   python labelu_json_to_voc_xml.py --input-json "xxx.json" --output-dir "xxx/labels" --folder images
"""

import argparse
import json
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom


# 平台内置默认值（建议通过前端/接口传参覆盖）
INPUT_JSON = ""
OUTPUT_DIR = ""
FOLDER_NAME = "images"


def _normalize_arg(value: str) -> str:
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1].strip()
    return text


def _pretty_xml(element: ET.Element) -> str:
    raw = ET.tostring(element, encoding="unicode")
    return minidom.parseString(raw).toprettyxml(indent="  ", encoding=None)


def labelu_to_voc_xml(input_json: str, output_dir: str, image_folder: str = "images"):
    os.makedirs(output_dir, exist_ok=True)

    with open(input_json, "r", encoding="utf-8") as f:
        records = json.load(f)

    converted = 0
    for record in records:
        filename = record.get("fileName", "unknown.jpg")
        result_str = record.get("result", "{}")
        result_obj = json.loads(result_str) if isinstance(result_str, str) else result_str

        width = result_obj.get("width", 0)
        height = result_obj.get("height", 0)
        depth = 3

        annotation = ET.Element("annotation")
        ET.SubElement(annotation, "folder").text = image_folder
        ET.SubElement(annotation, "filename").text = filename
        ET.SubElement(annotation, "path").text = f"./{image_folder}/{filename}"

        source = ET.SubElement(annotation, "source")
        ET.SubElement(source, "database").text = "Unknown"

        size = ET.SubElement(annotation, "size")
        ET.SubElement(size, "width").text = str(width)
        ET.SubElement(size, "height").text = str(height)
        ET.SubElement(size, "depth").text = str(depth)
        ET.SubElement(annotation, "segmented").text = "0"

        extra_annotations = [
            ann for ann in result_obj.get("annotations", [])
            if ann.get("toolName") != "rectTool"
        ]
        if extra_annotations:
            ET.SubElement(annotation, "extra_annotations").text = json.dumps(
                extra_annotations, ensure_ascii=False
            )

        for ann in result_obj.get("annotations", []):
            if ann.get("toolName") != "rectTool":
                continue
            for box in ann.get("result", []):
                label = box.get("label", "unknown")
                x = float(box.get("x", 0))
                y = float(box.get("y", 0))
                w = float(box.get("width", 0))
                h = float(box.get("height", 0))
                attributes = box.get("attributes", {})

                obj = ET.SubElement(annotation, "object")
                ET.SubElement(obj, "name").text = label
                ET.SubElement(obj, "pose").text = "Unspecified"
                ET.SubElement(obj, "truncated").text = "0"
                ET.SubElement(obj, "difficult").text = "0"
                if attributes:
                    ET.SubElement(obj, "attributes").text = json.dumps(attributes, ensure_ascii=False)

                bndbox = ET.SubElement(obj, "bndbox")
                ET.SubElement(bndbox, "xmin").text = str(int(round(x)))
                ET.SubElement(bndbox, "ymin").text = str(int(round(y)))
                ET.SubElement(bndbox, "xmax").text = str(int(round(x + w)))
                ET.SubElement(bndbox, "ymax").text = str(int(round(y + h)))

        stem = os.path.splitext(filename)[0]
        out_path = os.path.join(output_dir, f"{stem}.xml")
        xml_str = _pretty_xml(annotation)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(xml_str)
        converted += 1

    print(f"Converted {converted} LabelU records -> VOC XML in {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="LabelU JSON -> VOC XML (platform local)")
    parser.add_argument("--input-json", default=INPUT_JSON, help="LabelU JSON file path")
    parser.add_argument("--output-dir", default=OUTPUT_DIR, help="Output directory for XML files")
    parser.add_argument("--folder", default=FOLDER_NAME, help="VOC <folder> tag value")
    args = parser.parse_args()

    input_json = _normalize_arg(args.input_json)
    output_dir = _normalize_arg(args.output_dir)
    folder = _normalize_arg(args.folder) or "images"

    if not input_json:
        raise SystemExit("input-json 不能为空")
    if not output_dir:
        raise SystemExit("output-dir 不能为空")

    labelu_to_voc_xml(input_json, output_dir, folder)


if __name__ == "__main__":
    main()
