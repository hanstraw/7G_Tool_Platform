"""
Annotation format converters:
  - PASCAL VOC XML (one file per image) <-> LabelU JSON (one file per task)
"""

import json
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom


# ─────────────────────────────────────────────────────────────
# VOC XML → LabelU JSON
# ─────────────────────────────────────────────────────────────

def voc_xml_to_labelu(xml_dir: str, output_json: str, image_base_url: str = "/api/v1/tasks/attachment/upload/1"):
    """
    Convert a directory of PASCAL VOC XML files into a single LabelU JSON file.

    Args:
        xml_dir:        Directory containing .xml annotation files.
        output_json:    Output path for the LabelU JSON file.
        image_base_url: URL prefix used in the LabelU 'url' field.
    """
    records = []
    xml_files = sorted(f for f in os.listdir(xml_dir) if f.lower().endswith(".xml"))

    for idx, xml_file in enumerate(xml_files, start=1):
        xml_path = os.path.join(xml_dir, xml_file)
        tree = ET.parse(xml_path)
        root = tree.getroot()

        filename = root.findtext("filename", default=xml_file.replace(".xml", ".jpg"))
        width = int(root.findtext("size/width", default="0"))
        height = int(root.findtext("size/height", default="0"))
        folder = root.findtext("path", default=f"./data/{filename}")

        rect_results = []
        order = 1
        for obj in root.findall("object"):
            label = obj.findtext("name", default="unknown")
            bndbox = obj.find("bndbox")
            if bndbox is None:
                continue
            xmin = float(bndbox.findtext("xmin", "0"))
            ymin = float(bndbox.findtext("ymin", "0"))
            xmax = float(bndbox.findtext("xmax", "0"))
            ymax = float(bndbox.findtext("ymax", "0"))

            attr_text = obj.findtext("attributes")
            attributes = json.loads(attr_text) if attr_text else {}

            rect_results.append({
                "id": f"voc_{idx}_{order}",
                "x": xmin,
                "y": ymin,
                "label": label,
                "width": xmax - xmin,
                "height": ymax - ymin,
                "order": order,
                "attributes": attributes
            })
            order += 1

        # Restore non-rectTool annotations saved in <extra_annotations>
        extra_text = root.findtext("extra_annotations")
        extra_annotations = json.loads(extra_text) if extra_text else []

        annotations = extra_annotations + [{"toolName": "rectTool", "result": rect_results}]

        result_obj = {
            "width": width,
            "height": height,
            "rotate": 0,
            "annotations": annotations
        }

        records.append({
            "id": idx,
            "result": json.dumps(result_obj, ensure_ascii=False),
            "folder": os.path.dirname(folder) or "./data",
            "url": f"{image_base_url}/{filename}",
            "fileName": filename
        })

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"Converted {len(records)} VOC XML files → {output_json}")


# ─────────────────────────────────────────────────────────────
# LabelU JSON → VOC XML
# ─────────────────────────────────────────────────────────────

def _pretty_xml(element: ET.Element) -> str:
    raw = ET.tostring(element, encoding="unicode")
    return minidom.parseString(raw).toprettyxml(indent="  ", encoding=None)


def labelu_to_voc_xml(input_json: str, output_dir: str, image_folder: str = "images"):
    """
    Convert a LabelU JSON file into per-image PASCAL VOC XML files.

    Args:
        input_json:    Path to the LabelU JSON annotation file.
        output_dir:    Directory where XML files will be written.
        image_folder:  Value written into the VOC <folder> tag.
    """
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

        # Store non-rectTool annotations (tagTool, textTool, etc.) as a JSON extension field
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
        # minidom adds an XML declaration line; write as utf-8
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(xml_str)

        converted += 1

    print(f"Converted {converted} LabelU records → VOC XML in {output_dir}")


# ─────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert between PASCAL VOC XML and LabelU JSON")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_voc2lu = sub.add_parser("voc2labelu", help="VOC XML dir → LabelU JSON")
    p_voc2lu.add_argument("xml_dir", help="Directory with VOC XML files")
    p_voc2lu.add_argument("output_json", help="Output LabelU JSON path")
    p_voc2lu.add_argument("--base-url", default="/api/v1/tasks/attachment/upload/1")

    p_lu2voc = sub.add_parser("labelu2voc", help="LabelU JSON → VOC XML dir")
    p_lu2voc.add_argument("input_json", help="LabelU JSON file")
    p_lu2voc.add_argument("output_dir", help="Output directory for XML files")
    p_lu2voc.add_argument("--folder", default="images", help="VOC <folder> tag value")

    args = parser.parse_args()

    if args.cmd == "voc2labelu":
        voc_xml_to_labelu(args.xml_dir, args.output_json, args.base_url)
    elif args.cmd == "labelu2voc":
        labelu_to_voc_xml(args.input_json, args.output_dir, args.folder)
