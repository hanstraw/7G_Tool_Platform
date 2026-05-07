import os
import shutil
import xml.etree.ElementTree as ET
from PIL import Image
import sys

# 动态加载 01_convert_annotations.py
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
convert_annotations_path = os.path.join(base_dir, "04_数据质检与分析", "01_convert_annotations.py")

if os.path.exists(convert_annotations_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("convert_annotations", convert_annotations_path)
    convert_annotations = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(convert_annotations)
else:
    print(f"【错误】找不到 {convert_annotations_path}")
    sys.exit(1)

def merge_team_data(raw_dir, merged_raw_images, merged_raw_labels):
    os.makedirs(merged_raw_images, exist_ok=True)
    os.makedirs(merged_raw_labels, exist_ok=True)
    
    print("\n--- 开始在 raw/ 目录下扫描并聚合标注数据 ---")
    
    task_dirs = set()
    for root, _, files in os.walk(raw_dir):
        for file in files:
            if file.lower().endswith('.json') and file != "failed_images.json":
                task_dirs.add(root)
                
    if not task_dirs:
        print("  - [警告] 在 raw/ 目录下未找到任何 JSON 标注文件！")
        return
        
    for annotator_dir in task_dirs:
        rel_path = os.path.relpath(annotator_dir, raw_dir)
        if rel_path == ".":
            prefix = "main"
        else:
            prefix = rel_path.replace(os.sep, "_").replace(" ", "_")
            
        print(f"\n>> 正在处理数据夹: {annotator_dir} (前缀: {prefix})")
        
        json_files = [f for f in os.listdir(annotator_dir) if f.lower().endswith('.json') and f != "failed_images.json"]
        
        temp_xml_dir = os.path.abspath(os.path.join(merged_raw_labels, f"../temp_xmls_{prefix}"))
        os.makedirs(temp_xml_dir, exist_ok=True)
        
        for j_file in json_files:
            json_path = os.path.join(annotator_dir, j_file)
            print(f"  - 转换 JSON: {j_file}")
            try:
                convert_annotations.labelu_to_voc_xml(input_json=json_path, output_dir=temp_xml_dir)
            except Exception as e:
                print(f"  - [警告] JSON转换失败: {e}")
                
        valid_count = 0
        for root, dirs, files in os.walk(annotator_dir):
            if root != annotator_dir and root in task_dirs:
                continue
                
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                    img_path = os.path.join(root, file)
                    base_name = os.path.splitext(file)[0]
                    xml_path = os.path.join(temp_xml_dir, base_name + ".xml")
                    
                    if not os.path.exists(xml_path):
                        continue
                        
                    new_img_name = f"{prefix}_{file}"
                    new_xml_name = f"{prefix}_{base_name}.xml"
                    
                    new_img_path = os.path.join(merged_raw_images, new_img_name)
                    new_xml_path = os.path.join(merged_raw_labels, new_xml_name)
                    
                    shutil.copy2(img_path, new_img_path)
                    
                    try:
                        tree = ET.parse(xml_path)
                        xml_root = tree.getroot()
                        
                        file_tag = xml_root.find('filename')
                        if file_tag is not None:
                            file_tag.text = new_img_name
                        else:
                            file_tag = ET.SubElement(xml_root, 'filename')
                            file_tag.text = new_img_name
                            
                        path_tag = xml_root.find('path')
                        if path_tag is not None:
                            path_tag.text = new_img_name
                            
                        tree.write(new_xml_path, encoding='utf-8', xml_declaration=True)
                        valid_count += 1
                    except Exception as e:
                        print(f"  - [警告] 无法处理 XML {xml_path}: {e}")
                        
        print(f"  - 成功汇聚 {valid_count} 组数据。")
        
        try:
            shutil.rmtree(temp_xml_dir)
        except Exception:
            pass

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw_dir = os.path.join(base_dir, "raw")
    merged_raw_dir = os.path.join(base_dir, "temp_merged")
    merged_images = os.path.join(merged_raw_dir, "images")
    merged_labels = os.path.join(merged_raw_dir, "labels")
    
    if not os.path.exists(raw_dir):
        print("【错误】: 未找到 aw 文件夹！请在项目根目录下创建 aw 文件夹并放入标注数据。")
    else:
        merge_team_data(raw_dir, merged_images, merged_labels)
