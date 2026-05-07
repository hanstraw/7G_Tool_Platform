import os
import shutil
import random
import xml.etree.ElementTree as ET

# -------------------------- 工具函数：XML 转 YOLO TXT --------------------------
def xml_to_yolo(xml_path, class_list):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    size = root.find('size')
    w = int(size.find('width').text)
    h = int(size.find('height').text)

    yolo_lines = []
    for obj in root.iter('object'):
        cls = obj.find('name').text
        if cls not in class_list:
            continue
        cls_id = class_list.index(cls)
        xmlbox = obj.find('bndbox')
        xmin = float(xmlbox.find('xmin').text)
        ymin = float(xmlbox.find('ymin').text)
        xmax = float(xmlbox.find('xmax').text)
        ymax = float(xmlbox.find('ymax').text)

        x = (xmin + xmax) / 2.0 / w
        y = (ymin + ymax) / 2.0 / h
        bw = (xmax - xmin) / w
        bh = (ymax - ymin) / h

        yolo_lines.append(f"{cls_id} {x:.6f} {y:.6f} {bw:.6f} {bh:.6f}")
    return yolo_lines

# -------------------------- 数据集转换 + 划分 --------------------------
def prepare_yolo_dataset(
    src_dir,        # 原始目录：images + labels(xml)
    output_dir,     # 输出新目录
    class_names     # 类别列表，逗号分隔
):
    src_images = os.path.join(src_dir, "images")
    src_labels = os.path.join(src_dir, "labels")
    class_list = [c.strip() for c in class_names.split(",")]

    # 创建输出结构
    out = {
        "train_img": os.path.join(output_dir, "images", "train"),
        "val_img": os.path.join(output_dir, "images", "val"),
        "test_img": os.path.join(output_dir, "images", "test"),
        "train_lab": os.path.join(output_dir, "labels", "train"),
        "val_lab": os.path.join(output_dir, "labels", "val"),
        "test_lab": os.path.join(output_dir, "labels", "test"),
        "train_xml": os.path.join(output_dir, "labelsxml", "train"),
        "val_xml": os.path.join(output_dir, "labelsxml", "val"),
        "test_xml": os.path.join(output_dir, "labelsxml", "test"),
    }
    for d in out.values():
        os.makedirs(d, exist_ok=True)

    # 读取图片
    img_exts = ('.jpg', '.jpeg', '.png', '.bmp')
    img_files = [f for f in os.listdir(src_images) if f.lower().endswith(img_exts)]
    random.seed(42)
    random.shuffle(img_files)
    total = len(img_files)

    # 7:2:1
    train_end = int(total * 0.7)
    val_end = train_end + int(total * 0.2)
    splits = {
        "train": img_files[:train_end],
        "val": img_files[train_end:val_end],
        "test": img_files[val_end:]
    }

    print(f"总图片：{total}")
    for k, v in splits.items():
        print(f"{k}: {len(v)} 张")

    # 复制图片 + 生成TXT标签
    for split_name, files in splits.items():
        for img in files:
            # 复制图片
            shutil.copy2(
                os.path.join(src_images, img),
                os.path.join(output_dir, "images", split_name, img)
            )
            # 转换标签
            base = os.path.splitext(img)[0]
            xml_file = os.path.join(src_labels, f"{base}.xml")
            txt_file = os.path.join(output_dir, "labels", split_name, f"{base}.txt")

            if os.path.exists(xml_file):
                lines = xml_to_yolo(xml_file, class_list)
                with open(txt_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                shutil.copy2(xml_file, os.path.join(output_dir, "labelsxml", split_name, f"{base}.xml"))

    print("XML -> TXT 转换完成")
    print("7:2:1 划分完成")

# -------------------------- 生成YAML --------------------------
def make_yaml(output_dir, class_names):
    class_list = [c.strip() for c in class_names.split(",")]
    abs_path = os.path.abspath(output_dir)
    NL = chr(10)

    dataset_yaml = os.path.join(output_dir, "dataset.yaml")
    with open(dataset_yaml, "w", encoding="utf-8") as f:
        f.write("path: ./data" + NL)
        f.write("train: images/train" + NL)
        f.write("val: images/val" + NL)
        f.write("test: images/test" + NL)
        f.write("nc: " + str(len(class_list)) + NL)
        f.write("names: " + str(class_list) + NL)
    print(f"dataset.yaml 已生成：{dataset_yaml}")

    test_yaml = os.path.join(output_dir, "test.yaml")
    with open(test_yaml, "w", encoding="utf-8") as f:
        f.write("path: ./data" + NL)
        f.write("test: images/test" + NL)
        f.write("nc: " + str(len(class_list)) + NL)
        f.write("names: " + str(class_list) + NL)
    print(f"test.yaml 已生成：{test_yaml}")

# ===================== 执行 =====================
if __name__ == "__main__":
    # 原始数据（不动）
    src = r"E:\071garbage"

    # 输出新数据集
    out =r"E:\071garbage\datanew"

    # 你的类别（必须和XML里的name一致）
    labels = "garbage_street_scattered,garbage_street_can,garbage_street_dump,object_box,garbage_street_pack,non_garbage"

    # 运行
    prepare_yolo_dataset(src, out, labels)
    make_yaml(out, labels)
    print("\n全部完成！直接用于 YOLO 训练！")