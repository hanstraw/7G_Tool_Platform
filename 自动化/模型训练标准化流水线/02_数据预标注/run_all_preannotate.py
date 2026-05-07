"""
批量预标注脚本
对8个文件夹分别运行 YOLO 预标注，每个文件夹独立输出。
"""

import io
import subprocess
import sys
import time

# 修复 Windows GBK 编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import shutil
from pathlib import Path

import yaml


# 8个目标文件夹
FOLDERS = ["cc2", "zx2", "lxl2", "sy2", "wly2", "ymt2", "yyj2", "zzx2"]

# 项目根目录
ROOT = Path(__file__).resolve().parent
PREANNOTATE_DIR = ROOT / "labelu_yolo_preannotate"
PREANNOTATE_SCRIPT = PREANNOTATE_DIR / "preannotate.py"
BASE_CONFIG = PREANNOTATE_DIR / "config.yaml"

# 模型权重路径
MODEL_WEIGHTS = Path(r"C:\Users\Xiao\Desktop\预标注2\best0430.pt")


def create_folder_config(folder_name: str) -> Path:
    """为每个文件夹创建独立的配置文件"""
    config = yaml.safe_load(BASE_CONFIG.read_text(encoding="utf-8"))

    # 修改图片目录指向对应文件夹
    config["paths"]["image_dir"] = f"../{folder_name}"

    # 修改输出路径，每个文件夹独立输出
    config["paths"]["output_json"] = f"output/{folder_name}/labelu_yolo_{folder_name}.json"

    # 修改 checkpoint 路径，每个文件夹独立 checkpoint
    config["paths"]["checkpoint_jsonl"] = f"output/{folder_name}/checkpoint.jsonl"

    # 修改模型权重路径为绝对路径
    config["model"]["weights"] = str(MODEL_WEIGHTS)

    # 每次重新开始
    config["run"]["overwrite_checkpoint"] = True

    # 写入独立配置文件
    config_path = PREANNOTATE_DIR / f"config_{folder_name}.yaml"
    config_path.write_text(
        yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return config_path


def main():
    print(f"模型权重: {MODEL_WEIGHTS}")
    if not MODEL_WEIGHTS.exists():
        print(f"错误: 模型权重文件不存在: {MODEL_WEIGHTS}")
        sys.exit(1)

    if not PREANNOTATE_SCRIPT.exists():
        print(f"错误: 预标注脚本不存在: {PREANNOTATE_SCRIPT}")
        sys.exit(1)

    print(f"预标注脚本: {PREANNOTATE_SCRIPT}")
    print(f"基础配置: {BASE_CONFIG}")
    print(f"待处理文件夹: {', '.join(FOLDERS)}")
    print("=" * 60)

    results = {}
    total_start = time.time()

    for i, folder_name in enumerate(FOLDERS, start=1):
        folder_path = ROOT / folder_name
        if not folder_path.exists():
            print(f"\n[{i}/{len(FOLDERS)}] 跳过 {folder_name}: 文件夹不存在")
            results[folder_name] = "跳过(不存在)"
            continue

        print(f"\n{'=' * 60}")
        print(f"[{i}/{len(FOLDERS)}] 开始处理: {folder_name}")
        print(f"{'=' * 60}")

        # 创建独立配置
        config_path = create_folder_config(folder_name)
        print(f"配置文件: {config_path}")

        # 确保输出目录存在
        output_dir = PREANNOTATE_DIR / "output" / folder_name
        output_dir.mkdir(parents=True, exist_ok=True)

        # 运行预标注
        folder_start = time.time()
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(PREANNOTATE_SCRIPT),
                    "--config", config_path.name,
                    "--restart",
                ],
                cwd=str(PREANNOTATE_DIR),
                check=True,
            )
            elapsed = time.time() - folder_start
            print(f"\n[OK] {folder_name} 完成，耗时 {elapsed:.1f}s")
            results[folder_name] = f"成功 ({elapsed:.1f}s)"
        except subprocess.CalledProcessError as e:
            elapsed = time.time() - folder_start
            print(f"\n[FAIL] {folder_name} 失败，耗时 {elapsed:.1f}s，返回码: {e.returncode}")
            results[folder_name] = f"失败 (返回码 {e.returncode})"
        except Exception as e:
            elapsed = time.time() - folder_start
            print(f"\n[FAIL] {folder_name} 异常: {e}")
            results[folder_name] = f"异常: {e}"
        finally:
            # 清理临时配置文件
            config_path.unlink(missing_ok=True)

    total_elapsed = time.time() - total_start

    print(f"\n{'=' * 60}")
    print("全部完成! 汇总:")
    print(f"{'=' * 60}")
    for folder_name, status in results.items():
        output_json = PREANNOTATE_DIR / "output" / folder_name / f"labelu_yolo_{folder_name}.json"
        exists = "[OK]" if output_json.exists() else "[--]"
        print(f"  {exists} {folder_name}: {status}")
        if output_json.exists():
            print(f"    输出: {output_json}")
    print(f"\n总耗时: {total_elapsed:.1f}s ({total_elapsed/60:.1f}分钟)")


if __name__ == "__main__":
    main()
