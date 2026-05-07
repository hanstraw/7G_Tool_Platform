import os
import shutil
import xml.etree.ElementTree as ET
from PIL import Image

def clean_data(raw_images_dir, raw_labels_dir, clean_images_dir, clean_labels_dir):
    os.makedirs(clean_images_dir, exist_ok=True)
    os.makedirs(clean_labels_dir, exist_ok=True)
    
    print("\n--- 开始标准化清洗数据 ---")
    valid_count = 0
    removed_count = 0
    
    images = [f for f in os.listdir(raw_images_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
    for img_name in images:
        if "gamma" in img_name.lower() or "thumbnail" in img_name.lower():
            removed_count += 1
            continue
            
        base_name = os.path.splitext(img_name)[0]
        xml_name = base_name + ".xml"
        xml_path = os.path.join(raw_labels_dir, xml_name)
        img_path = os.path.join(raw_images_dir, img_name)
        
        if not os.path.exists(xml_path):
            removed_count += 1
            continue
            
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
        except Exception:
            removed_count += 1
            continue
            
        objects = root.findall('object')
        if not objects:
            removed_count += 1
            continue
            
        size_elem = root.find('size')
        if size_elem is None:
            try:
                with Image.open(img_path) as im:
                    w, h = im.size
                    d = len(im.getbands())
                size_elem = ET.SubElement(root, 'size')
                ET.SubElement(size_elem, 'width').text = str(w)
                ET.SubElement(size_elem, 'height').text = str(h)
                ET.SubElement(size_elem, 'depth').text = str(d)
            except Exception:
                removed_count += 1
                continue
        else:
            w_text = size_elem.find('width').text if size_elem.find('width') is not None else '0'
            h_text = size_elem.find('height').text if size_elem.find('height') is not None else '0'
            try:
                w, h = int(w_text), int(h_text)
            except ValueError:
                w, h = 0, 0
            if w == 0 or h == 0:
                removed_count += 1
                continue
                
        file_tag = root.find('filename')
        if file_tag is not None and file_tag.text != img_name:
            file_tag.text = img_name
            
        shutil.copy2(img_path, os.path.join(clean_images_dir, img_name))
        tree.write(os.path.join(clean_labels_dir, xml_name), encoding='utf-8', xml_declaration=True)
        valid_count += 1
        
    print(f"数据清洗完成。保留: {valid_count} 个对齐样本，剔除: {removed_count} 个不合规样本")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    merged_raw_dir = os.path.join(base_dir, "temp_merged")
    merged_images = os.path.join(merged_raw_dir, "images")
    merged_labels = os.path.join(merged_raw_dir, "labels")
    
    clean_dir = os.path.join(base_dir, "temp_clean")
    clean_images = os.path.join(clean_dir, "images")
    clean_labels = os.path.join(clean_dir, "labels")

    if not os.path.exists(merged_images) or not os.listdir(merged_images):
        print("【错误】: 请先运行 01_merge_team_data.py！")
    else:
        clean_data(merged_images, merged_labels, clean_images, clean_labels)
