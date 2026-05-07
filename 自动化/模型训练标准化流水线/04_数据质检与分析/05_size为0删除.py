import os
import xml.etree.ElementTree as ET

# 定义文件夹路径
# xml_folder_path = r'D:\7g\zijinghua\xrjcLjbl0822\12yuexingren\winderperson\labels'
xml_folder_path = r'D:\7g\2502\poop\zenqiang\labels'

# 遍历文件夹中的所有XML文件
for filename in os.listdir(xml_folder_path):
    if filename.endswith('.xml'):
        # 构建XML文件的完整路径
        xml_file_path = os.path.join(xml_folder_path, filename)
        
        # 解析XML文件
        try:
            tree = ET.parse(xml_file_path)
            root = tree.getroot()
        except ET.ParseError:
            print(f"Error parsing {xml_file_path}. Skipping...")
            continue

        # 获取size元素
        size_elem = root.find('size')
        if size_elem is None:
            print(f"No 'size' element found in {xml_file_path}. Skipping...")
            continue

        # 获取width和height的值
        width = int(size_elem.find('width').text)
        height = int(size_elem.find('height').text)

        # 检查width和height是否都为0
        if width == 0 and height == 0:
            print(f"Deleting {xml_file_path} because width and height are both 0.")
            os.remove(xml_file_path)  # 删除文件

print("XML file check and deletion complete.")