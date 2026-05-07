import os
import shutil


def filter_files(source_dir, target_dir):
    """
    过滤文件夹: 文件名包含 thumbnail 的跳过, 不包含的复制到目标文件夹
    :param source_dir: 源文件夹路径
    :param target_dir: 目标文件夹路径
    """
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    skipped = 0
    copied = 0
    for filename in os.listdir(source_dir):
        source_path = os.path.join(source_dir, filename)
        if not os.path.isfile(source_path):
            continue
        if "thumbnail" in filename.lower():
            print(f"已跳过: {filename}")
            skipped += 1
        else:
            shutil.copy2(source_path, os.path.join(target_dir, filename))
            print(f"已复制: {filename}")
            copied += 1

    print(f"\n完成 — 复制: {copied} 个, 跳过: {skipped} 个")


# ====================== 你只需要修改这里 ======================
SOURCE_FOLDER = r"E:\071garbage\media\upload\1"
TARGET_FOLDER = r"E:\071garbage\media\upload\images_no_thumbnail"
# =============================================================

if __name__ == "__main__":
    filter_files(SOURCE_FOLDER, TARGET_FOLDER)
