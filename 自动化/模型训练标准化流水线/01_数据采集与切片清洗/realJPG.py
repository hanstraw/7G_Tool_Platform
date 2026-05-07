import os
import cv2
import imghdr
from tqdm import tqdm  # 进度条工具，可选

def is_valid_jpg(img_path):
    """检查文件是否为有效的JPG格式"""
    try:
        # 先用imghdr检查基础格式
        if imghdr.what(img_path) != 'jpeg':
            return False
        
        # 再用cv2深度验证
        img = cv2.imread(img_path)
        if img is None:
            return False
            
        # 尝试解码验证
        if not cv2.imencode('.jpg', img)[0]:
            return False
            
        return True
    except Exception as e:
        print(f"验证异常 {img_path}: {str(e)}")
        return False

def reencode_jpg(src_path, dst_path, quality=95):
    """重新编码JPG文件"""
    try:
        img = cv2.imread(src_path)
        if img is None:
            raise ValueError("无法读取图像数据")
            
        # 参数说明：质量(0-100)，优化标志
        success = cv2.imwrite(dst_path, img, 
                            [int(cv2.IMWRITE_JPEG_QUALITY), quality,
                             int(cv2.IMWRITE_JPEG_OPTIMIZE), 1])
        if not success:
            raise RuntimeError("cv2.imwrite失败")
        return True
    except Exception as e:
        print(f"重新编码失败 {src_path} -> {dst_path}: {str(e)}")
        return False

def process_directory(input_dir, output_dir=None, overwrite=False):
    """
    处理目录中的所有JPG文件
    :param input_dir: 输入目录
    :param output_dir: 输出目录（None则覆盖原文件）
    :param overwrite: 是否覆盖已有输出文件
    """
    if output_dir is None:
        output_dir = input_dir
    else:
        os.makedirs(output_dir, exist_ok=True)

    bad_files = []
    total_files = 0

    # 收集所有JPG文件（包括子目录）
    file_list = []
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg')):
                file_list.append(os.path.join(root, file))

    print(f"发现 {len(file_list)} 个JPG文件")

    # 处理文件
    for src_path in tqdm(file_list, desc="处理进度"):
        total_files += 1
        
        # 构建输出路径
        if output_dir == input_dir:
            dst_path = src_path
        else:
            rel_path = os.path.relpath(src_path, input_dir)
            dst_path = os.path.join(output_dir, rel_path)
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)

        # 跳过已处理文件（如果不需要覆盖）
        if not overwrite and os.path.exists(dst_path):
            continue

        # 检查并重新编码
        if not is_valid_jpg(src_path):
            print(f"\n发现损坏/非标准文件: {src_path}")
            if reencode_jpg(src_path, dst_path):
                bad_files.append(src_path)
                print(f"已重新编码 -> {dst_path}")
            else:
                print(f"重新编码失败: {src_path}")

    # 生成报告
    print("\n" + "="*50)
    print(f"处理完成！扫描 {total_files} 个文件")
    print(f"发现并处理 {len(bad_files)} 个问题文件：")
    for f in bad_files:
        print(f"  - {f}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='JPG文件验证和重新编码工具')
    parser.add_argument('input_dir', help='输入目录路径')
    parser.add_argument('--output_dir', help='输出目录路径（默认覆盖原文件）')
    parser.add_argument('--overwrite', action='store_true', help='覆盖已有输出文件')
    
    args = parser.parse_args()
    
    process_directory(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        overwrite=args.overwrite
    )

    # python realJPG.py D:\7g\2507\test --overwrite

    # python jpg_validator.py /path/to/images --output_dir /path/to/fixed_images