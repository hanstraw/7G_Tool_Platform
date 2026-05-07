import os
import shutil

def filter_files(source_dir, target_dir):
    """
    过滤文件夹：文件名包含 gamma 的跳过，不包含的复制到目标文件夹
    :param source_dir: 源文件夹路径
    :param target_dir: 目标文件夹路径
    """
    # 如果目标文件夹不存在，自动创建
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    # 遍历源文件夹下所有文件
    for filename in os.listdir(source_dir):
        # 构建完整文件路径
        source_path = os.path.join(source_dir, filename)

        # 只处理文件，跳过文件夹
        if os.path.isfile(source_path):
            # 判断文件名是否包含 gamma（不区分大小写）
            if "gamma" not in filename.lower():
                target_path = os.path.join(target_dir, filename)
                # 复制文件到目标文件夹
                shutil.copy2(source_path, target_path)
                print(f"已复制：{filename}")

# ====================== 你只需要修改这里 ======================
# 源文件夹（你要过滤的文件夹）
SOURCE_FOLDER = r"E:\070garbage\labels"
# 目标文件夹（符合条件的文件保存到这里）
TARGET_FOLDER = r"E:\071garbage\labels"
# =============================================================

if __name__ == "__main__":
    filter_files(SOURCE_FOLDER, TARGET_FOLDER)
    print("文件过滤完成！")