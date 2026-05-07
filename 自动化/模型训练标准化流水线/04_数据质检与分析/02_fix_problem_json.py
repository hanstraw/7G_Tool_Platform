import json
import os
import glob

folder_path = r'c:\Users\Xiao\Desktop\类别问题处理'

# 之前发现的有问题的类别映射表
label_map = {
    "StreetVendor_catering": "streetVendor_catering",
    "StreetVendor_fruit": "streetVendor_fruit",
    "StreetVendor_other": "streetVendor_other",
    "StreetVendor_vegetable": "streetVendor_vegetablet",
    "streetVendor_vegetable": "streetVendor_vegetablet",
    "object_bauket": "object_bucket",
}

def process_directory(folder):
    # 获取目录下所有 json 文件
    json_files = glob.glob(os.path.join(folder, '*.json'))
    
    for input_file in json_files:
        # 忽略已经修复过的文件
        if input_file.endswith('_fixed.json'):
            continue
            
        print(f"正在扫描: {os.path.basename(input_file)}")
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"  读取失败: {e}")
            continue

        modified_count = 0
        total_labels_fixed = 0

        # 判断数据类型，正常 LabelU 导出是一个列表
        items = data if isinstance(data, list) else [data]

        # 遍历每张图片的数据
        for item in items:
            if isinstance(item, dict) and 'result' in item and isinstance(item['result'], str):
                try:
                    # 解析字符串形式的 result JSON
                    result_data = json.loads(item['result'])
                    item_modified = False
                    
                    # 遍历标注信息
                    if 'annotations' in result_data:
                        for ann in result_data['annotations']:
                            if 'result' in ann and isinstance(ann['result'], list):
                                for res in ann['result']:
                                    if 'label' in res:
                                        old_label = res['label']
                                        # 如果标签在映射表中，进行替换
                                        if old_label in label_map:
                                            res['label'] = label_map[old_label]
                                            item_modified = True
                                            total_labels_fixed += 1
                    
                    # 如果修改了内容，重新转回字符串
                    if item_modified:
                        item['result'] = json.dumps(result_data, ensure_ascii=False)
                        modified_count += 1
                except json.JSONDecodeError:
                    pass

        # 如果有修改，则生成 _fixed.json 文件
        if modified_count > 0:
            base_name = os.path.splitext(input_file)[0]
            output_file = f"{base_name}_fixed.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  -> 发现异常标签！修复了 {modified_count} 条数据，替换了 {total_labels_fixed} 个标签。")
            print(f"  -> 已生成修复文件: {os.path.basename(output_file)}")
        else:
            print(f"  -> 该文件正常，无错误标签跳过。")

if __name__ == '__main__':
    process_directory(folder_path)
