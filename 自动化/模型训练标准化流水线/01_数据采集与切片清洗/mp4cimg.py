from pathlib import Path
import csv
import time

import cv2


INPUT_FOLDERS = [
    "三元里飞鹅西路附近",
    "嘉禾广场流动摊贩",
    "万科"
]
OUTPUT_DIR = "output"
INTERVAL_SECONDS = 10
SUMMARY_FILENAME = "summary.csv"


def extract_frames_from_video(
    video_path: Path,
    output_dir: Path,
    interval_seconds: int,
    video_index: int,
) -> int:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"无法打开视频文件: {video_path}")
        return 0

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps else 0

    print(f"\n正在处理: {video_path.name}")
    print(f"视频信息: {total_frames} 帧, {fps:.2f} FPS, {duration:.2f} 秒")

    saved_count = 0
    start_time = time.time()
    current_second = 0

    while current_second <= duration:
        cap.set(cv2.CAP_PROP_POS_MSEC, current_second * 1000)
        ok, frame = cap.read()
        if not ok:
            break

        image_filename = f"video_{video_index:04d}_{saved_count:06d}_{current_second:06d}s.jpg"
        image_path = output_dir / image_filename

        ok, jpg_buffer = cv2.imencode(".jpg", frame)
        if not ok:
            print(f"保存失败: {image_path}")
            break
        image_path.write_bytes(jpg_buffer.tobytes())

        saved_count += 1
        if saved_count % 10 == 0:
            elapsed = time.time() - start_time
            print(f"已保存 {saved_count} 张，当前视频时间 {current_second:.0f}s，耗时 {elapsed:.2f}s")

        current_second += interval_seconds

    cap.release()
    elapsed = time.time() - start_time
    print(f"完成: {video_path.name}，保存 {saved_count} 张到 {output_dir}，耗时 {elapsed:.2f}s")
    return saved_count


def find_mp4_files(video_dir: Path) -> list[Path]:
    if not video_dir.exists():
        print(f"目录不存在: {video_dir}")
        return []

    video_files = sorted(video_dir.glob("*.mp4"))
    if not video_files:
        print(f"未找到 MP4 文件: {video_dir}")
        return []

    print(f"\n目录 {video_dir.name}: 找到 {len(video_files)} 个 MP4 文件")
    return video_files


def write_summary(summary_path: Path, rows: list[dict[str, object]]) -> None:
    with summary_path.open("w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(
            csvfile,
            fieldnames=["video_index", "video_file", "image_count"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n统计表已输出: {summary_path}")


def main() -> None:
    root_dir = Path(__file__).resolve().parent
    output_base_dir = root_dir / OUTPUT_DIR
    output_base_dir.mkdir(parents=True, exist_ok=True)

    print(f"每 {INTERVAL_SECONDS} 秒抽取 1 帧")
    print(f"输出目录: {output_base_dir}")

    grand_total = 0
    summary_rows = []
    video_files = []
    for folder_name in INPUT_FOLDERS:
        video_files.extend(find_mp4_files(root_dir / folder_name))

    for video_index, video_file in enumerate(video_files, start=1):
        saved_count = extract_frames_from_video(
            video_file,
            output_base_dir,
            INTERVAL_SECONDS,
            video_index,
        )
        grand_total += saved_count
        summary_rows.append(
            {
                "video_index": video_index,
                "video_file": str(video_file.relative_to(root_dir)),
                "image_count": saved_count,
            }
        )

    write_summary(output_base_dir / SUMMARY_FILENAME, summary_rows)
    print(f"\n全部处理完成，共保存 {grand_total} 张图片")


if __name__ == "__main__":
    main()
