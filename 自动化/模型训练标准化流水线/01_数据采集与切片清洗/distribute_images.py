import os
import shutil

def distribute_images():
    base_dir = r"c:\Users\Xiao\Desktop\街道图片2"
    data_dir = os.path.join(base_dir, "data")
    
    # 获取所有非 data 的目标文件夹，并排序
    target_folders = [f for f in os.listdir(base_dir) 
                      if os.path.isdir(os.path.join(base_dir, f)) and f != "data"]
    target_folders.sort()
    
    # 获取 data 文件夹中的所有图片（文件），并按名称排序
    if not os.path.exists(data_dir):
        print(f"错误: 找不到源文件夹 {data_dir}")
        return

    images = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
    images.sort()
    
    total_images = len(images)
    num_folders = len(target_folders)
    
    if num_folders == 0:
        print("错误: 没有找到目标文件夹！")
        return
        
    if total_images == 0:
        print("data 文件夹中没有找到图片。")
        return

    print(f"找到 {total_images} 张图片，准备分发到以下 {num_folders} 个文件夹:")
    print(target_folders)

    # 计算每个文件夹应该分配的数量
    base_count = total_images // num_folders
    remainder = total_images % num_folders
    
    current_idx = 0
    for i, target_folder in enumerate(target_folders):
        # 前 remainder 个文件夹多分配 1 张，以保证余数被分发完
        count = base_count + (1 if i < remainder else 0)
        
        assigned_images = images[current_idx : current_idx + count]
        current_idx += count
        
        target_path = os.path.join(base_dir, target_folder)
        print(f"正在向 {target_folder} 分发 {count} 张图片...")
        
        for image in assigned_images:
            src_path = os.path.join(data_dir, image)
            dst_path = os.path.join(target_path, image)
            # 使用 move 将文件移动走。如果想保留原文件，可以改为 shutil.copy(src_path, dst_path)
            shutil.move(src_path, dst_path)

    print("\n分发完成！")

if __name__ == "__main__":
    distribute_images()
