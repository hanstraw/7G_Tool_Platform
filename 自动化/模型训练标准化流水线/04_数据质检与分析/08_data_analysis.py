import json
import os
import xml.etree.ElementTree as ET

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from tqdm import tqdm

import matplotlib.font_manager as _fm

def _setup_chinese_font():
    candidates = [
        "SimHei", "Microsoft YaHei", "STXihei", "STHeiti", "FangSong", "KaiTi",
        "Noto Sans CJK SC", "Noto Sans CJK TC", "Noto Sans SC",
        "Noto Serif CJK SC", "Source Han Sans SC", "Source Han Serif SC",
        "WenQuanYi Micro Hei", "WenQuanYi Zen Hei",
        "PingFang SC", "Heiti SC", "STSong",
    ]
    available = {f.name for f in _fm.fontManager.ttflist}
    chosen = next((f for f in candidates if f in available), None)
    if chosen:
        matplotlib.rcParams["font.family"] = chosen
    else:
        fallback = next(
            (f for f in available if any(k in f for k in ("CJK", "Hei", "Song", "Gothic", "PuHui"))),
            None
        )
        if fallback:
            matplotlib.rcParams["font.family"] = fallback
    matplotlib.rcParams["axes.unicode_minus"] = False

_setup_chinese_font()

# ===================== 请修改路径 =====================
XML_DIR = r"./data/labelsxml"
SAVE_DIR = r"./results"
# ======================================================

# labelU tagTool key -> 中文标题
SCENE_FIELDS = {
    "sceneType": "场景类型",
    "lighting":  "光照条件",
    "weather":   "天气",
    "quality":   "图像质量",
    "angle":     "拍摄角度",
    "source":    "数据来源",
}


def safe_find_text(root, tag):
    node = root.find(tag)
    return node.text.strip() if node is not None and node.text else "unknown"


def safe_float_cast(val):
    try:
        return float(val)
    except Exception:
        return 0.0


def _parse_extra_annotations(root):
    """从 <extra_annotations> 读取 labelU tagTool 场景属性."""
    result = {k: "unknown" for k in SCENE_FIELDS}
    extra_text = root.findtext("extra_annotations")
    if not extra_text:
        # 兼容旧格式: 直接读顶层字段
        result["sceneType"] = safe_find_text(root, "scene")
        result["lighting"]  = safe_find_text(root, "lighting")
        result["weather"]   = safe_find_text(root, "weather")
        result["angle"]     = safe_find_text(root, "angle")
        return result
    try:
        annotations = json.loads(extra_text)
    except Exception:
        return result
    for ann in annotations:
        if ann.get("toolName") != "tagTool":
            continue
        for tag_item in ann.get("result", []):
            for key, val in tag_item.get("value", {}).items():
                if key in result:
                    # val 是列表时取第一个
                    result[key] = val[0] if isinstance(val, list) and val else str(val)
    return result


def collect_xml_files(xml_dir):
    xml_files = []
    for root_dir, _, files in os.walk(xml_dir):
        for file_name in files:
            if file_name.lower().endswith(".xml"):
                xml_path = os.path.join(root_dir, file_name)
                xml_files.append(os.path.relpath(xml_path, xml_dir))
    return sorted(xml_files)


def parse_xml(xml_path):
    if not os.path.exists(xml_path):
        print(f"[WARN] XML file does not exist, skipped: {xml_path}")
        return None

    if os.path.getsize(xml_path) == 0:
        print(f"[WARN] XML is empty, skipped: {xml_path}")
        return None

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as exc:
        print(f"[WARN] XML parse failed, skipped: {xml_path} ({exc})")
        return None
    except Exception as exc:
        print(f"[WARN] Failed to read XML, skipped: {xml_path} ({exc})")
        return None

    filename = safe_find_text(root, "filename")
    size = root.find("size")
    img_w = int(safe_float_cast(safe_find_text(size, "width"))) if size else 0
    img_h = int(safe_float_cast(safe_find_text(size, "height"))) if size else 0

    scene_attrs = _parse_extra_annotations(root)

    objects = []
    for obj in root.findall("object"):
        cls = safe_find_text(obj, "name")
        bndbox = obj.find("bndbox")
        if not bndbox:
            continue
        xmin = int(safe_float_cast(safe_find_text(bndbox, "xmin")))
        ymin = int(safe_float_cast(safe_find_text(bndbox, "ymin")))
        xmax = int(safe_float_cast(safe_find_text(bndbox, "xmax")))
        ymax = int(safe_float_cast(safe_find_text(bndbox, "ymax")))
        w = xmax - xmin
        h = ymax - ymin
        objects.append({
            "class": cls,
            "w": w, "h": h,
            "area": w * h,
            "norm_w": w / img_w if img_w else 0,
            "norm_h": h / img_h if img_h else 0,
            "img_w": img_w,
            "img_h": img_h,
            "occlusion":  safe_find_text(obj, "occlusion"),
            "difficulty": safe_find_text(obj, "difficulty"),
            **scene_attrs,
        })

    return {
        "filename": filename,
        "img_w": img_w, "img_h": img_h,
        "obj_count": len(objects),
        "objects": objects,
        **scene_attrs,
    }


# ─────────────────────────────────────────────────────────────
# 图表工具
# ─────────────────────────────────────────────────────────────

def _save_bar(series: pd.Series, title: str, xlabel: str, ylabel: str, fname: str, rotate: int = 0):
    fig, ax = plt.subplots(figsize=(max(6, len(series) * 0.7 + 2), 5))
    series.plot(kind="bar", ax=ax, color="#4C72B0", edgecolor="white")
    ax.set_title(title, fontsize=13)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=rotate)
    for bar in ax.patches:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                str(int(bar.get_height())), ha="center", va="bottom", fontsize=8)
    plt.tight_layout()
    path = os.path.join(SAVE_DIR, fname)
    plt.savefig(path, dpi=120)
    plt.close()
    return path


def _save_grouped_bar(df: pd.DataFrame, title: str, fname: str, rotate: int = 30):
    """df: index=场景值, columns=类别, values=数量."""
    fig, ax = plt.subplots(figsize=(max(8, len(df) * 1.2 + 2), 5))
    df.plot(kind="bar", ax=ax, edgecolor="white")
    ax.set_title(title, fontsize=13)
    ax.set_xlabel("")
    ax.set_ylabel("目标数量")
    ax.tick_params(axis="x", rotation=rotate)
    ax.legend(title="类别", bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)
    plt.tight_layout()
    path = os.path.join(SAVE_DIR, fname)
    plt.savefig(path, dpi=120)
    plt.close()
    return path


def _save_line(series: pd.Series, title: str, xlabel: str, ylabel: str, fname: str):
    fig, ax = plt.subplots(figsize=(max(6, len(series) * 0.6 + 2), 4))
    ax.plot(series.index.astype(str), series.values, marker="o", color="#4C72B0")
    ax.set_title(title, fontsize=13)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=30)
    plt.tight_layout()
    path = os.path.join(SAVE_DIR, fname)
    plt.savefig(path, dpi=120)
    plt.close()
    return path


def _md_img(rel_path: str, alt: str = "") -> str:
    return f"![{alt}]({os.path.basename(rel_path)})\n"


# ─────────────────────────────────────────────────────────────
# 主分析
# ─────────────────────────────────────────────────────────────

def run_analysis(xml_dir=None, save_dir=None):
    global XML_DIR, SAVE_DIR
    if xml_dir is not None: XML_DIR = xml_dir
    if save_dir is not None: SAVE_DIR = save_dir
    os.makedirs(SAVE_DIR, exist_ok=True)
    xml_files = collect_xml_files(XML_DIR)
    print(f"找到 XML: {len(xml_files)}")

    if not xml_files:
        print(f"[INFO] No XML files found under {XML_DIR}. Subfolders have been checked.")
        return

    img_list, obj_list = [], []
    for f in tqdm(xml_files, desc="解析中"):
        data = parse_xml(os.path.join(XML_DIR, f))
        if data:
            img_list.append(data)
            obj_list.extend(data["objects"])

    df_img = pd.DataFrame(img_list)
    df_obj = pd.DataFrame(obj_list) if obj_list else pd.DataFrame()

    if df_img.empty:
        print("[INFO] No valid XML content was parsed. Analysis report was not generated.")
        return

    md = ["# YOLOv11 数据集分析报告\n"]

    # ── 1. 基础信息 ──────────────────────────────────────────
    md.append("## 1. 基础信息\n")
    basic = {
        "总图片数": len(df_img),
        "总目标数": len(df_obj),
        "类别数": df_obj["class"].nunique() if not df_obj.empty else 0,
        "平均每图目标数": round(df_img["obj_count"].mean(), 2),
    }
    md.append(pd.DataFrame([basic]).T.rename(columns={0: "数值"}).to_markdown())
    md.append("\n")

    # ── 2. 类别分布 ──────────────────────────────────────────
    md.append("## 2. 类别样本分布\n")
    if not df_obj.empty:
        cls_cnt = df_obj["class"].value_counts()
        cls_df = pd.DataFrame({"数量": cls_cnt, "占比(%)": (cls_cnt / cls_cnt.sum() * 100).round(2)})
        md.append(cls_df.to_markdown())
        md.append("\n")
        p = _save_bar(cls_cnt, "各类别目标数量", "类别", "数量", "cls_dist.png", rotate=30)
        md.append(_md_img(p, "类别分布"))

    # ── 3. 单图目标数分布 ─────────────────────────────────────
    md.append("## 3. 单张图片目标数量分布\n")
    img_obj = df_img["obj_count"].value_counts().sort_index()
    if len(img_obj) > 15:
        p = _save_line(img_obj, "单图目标数分布", "目标数", "图片数", "img_obj_dist.png")
        md.append(_md_img(p, "单图目标数分布"))
    else:
        md.append(pd.DataFrame({"图片数量": img_obj}).to_markdown())
        md.append("\n")

    # ── 4. 目标尺寸统计 ───────────────────────────────────────
    md.append("## 4. 目标尺寸统计(像素)\n")
    if not df_obj.empty:
        md.append(df_obj[["w", "h", "area"]].describe().round(2).to_markdown())
        md.append("\n")

        # 4a. 尺寸分档(基于目标面积与图像面积的相对占比)
        md.append(
            "> **尺寸分档标准(相对面积占比 r = 目标面积 / 图像面积)**\n"
            "> | 档位 | 相对面积 r | 说明 |\n"
            "> | --- | --- | --- |\n"
            "> | tiny   | r < 0.0004              | 极小目标 |\n"
            "> | small  | 0.0004 <= r < 0.0025     | 小目标   |\n"
            "> | medium | 0.0025 <= r < 0.04       | 中等目标 |\n"
            "> | large  | r >= 0.04                | 大/超大目标 |\n\n"
        )
        SIZE_BINS = [
            ("tiny",   0,      0.0004),
            ("small",  0.0004, 0.0025),
            ("medium", 0.0025, 0.04),
            ("large",  0.04,   float("inf")),
        ]
        def _size_bin(row):
            r = row["area"] / (row["img_w"] * row["img_h"]) if row["img_w"] * row["img_h"] > 0 else 0
            for name, lo, hi in SIZE_BINS:
                if lo <= r < hi:
                    return name
            return "large"
        df_obj["size_bin"] = df_obj.apply(_size_bin, axis=1)
        bin_order = ["tiny", "small", "medium", "large"]
        bin_cnt = df_obj["size_bin"].value_counts().reindex(bin_order, fill_value=0)
        p = _save_bar(bin_cnt, "目标尺寸分档分布(相对面积占比)", "尺寸档", "目标数", "size_bin_dist.png")
        md.append(_md_img(p, "尺寸分档分布"))
        # 4b. 各类别 x 尺寸档交叉分析
        md.append("### 各类别尺寸分档分布\n")
        cross_size = df_obj.groupby(["class", "size_bin"]).size().unstack(fill_value=0)
        cross_size = cross_size.reindex(columns=[c for c in bin_order if c in cross_size.columns])
        md.append(cross_size.to_markdown())
        md.append("\n")
        p = _save_grouped_bar(cross_size, "各类别尺寸分档目标数量", "size_class_cross.png", rotate=30)
        md.append(_md_img(p, "类别x尺寸"))

        # 4c. 宽高散点图(按类别着色)
        fig, ax = plt.subplots(figsize=(7, 5))
        classes = df_obj["class"].unique()
        cmap = plt.get_cmap("tab10")
        for i, cls in enumerate(classes):
            sub = df_obj[df_obj["class"] == cls]
            ax.scatter(sub["w"], sub["h"], s=8, alpha=0.5, color=cmap(i % 10), label=cls)
        ax.set_title("目标宽高散点图")
        ax.set_xlabel("宽(px)")
        ax.set_ylabel("高(px)")
        ax.legend(title="类别", bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=7)
        plt.tight_layout()
        scatter_path = os.path.join(SAVE_DIR, "size_scatter.png")
        plt.savefig(scatter_path, dpi=120)
        plt.close()
        md.append(_md_img(scatter_path, "宽高散点图"))

    # ── 5. 分辨率分布 ─────────────────────────────────────────
    md.append("## 5. 图片分辨率分布\n")
    df_img["res"] = df_img["img_w"].astype(str) + "x" + df_img["img_h"].astype(str)
    res_cnt = df_img["res"].value_counts()
    md.append(pd.DataFrame({"图片数": res_cnt}).to_markdown())
    md.append("\n")

    # ── 6-11. 场景维度分布 + 各场景下类别交叉分析 ──────────────
    for field_idx, (field_key, field_name) in enumerate(SCENE_FIELDS.items(), start=6):
        if field_key not in df_img.columns:
            continue

        md.append(f"## {field_idx}. {field_name}分布\n")
        cnt = df_img[field_key].value_counts()

        # 分布图(柱状)
        p = _save_bar(cnt, f"{field_name}分布", field_name, "图片数",
                      f"scene_{field_key}.png", rotate=30)
        md.append(_md_img(p, f"{field_name}分布"))

        # 各场景值下的类别目标数交叉分析
        if not df_obj.empty and field_key in df_obj.columns:
            md.append(f"### {field_name} × 类别 交叉分析\n")
            cross = df_obj.groupby([field_key, "class"]).size().unstack(fill_value=0)
            # 表格
            md.append(cross.to_markdown())
            md.append("\n")
            # 分组柱状图
            p2 = _save_grouped_bar(
                cross,
                f"{field_name} × 类别 目标数量",
                f"scene_{field_key}_cross.png",
                rotate=30,
            )
            md.append(_md_img(p2, f"{field_name}×类别"))

    # ── 遮挡 & 难易 ───────────────────────────────────────────
    if not df_obj.empty:
        sec = len(SCENE_FIELDS) + 6

        md.append(f"## {sec}. 目标遮挡程度分布\n")
        occ = df_obj["occlusion"].value_counts()
        p = _save_bar(occ, "遮挡程度分布", "遮挡程度", "目标数", "occlusion_dist.png")
        md.append(_md_img(p, "遮挡分布"))

        md.append(f"## {sec + 1}. 检测难易程度分布\n")
        diff = df_obj["difficulty"].value_counts()
        p = _save_bar(diff, "检测难易程度分布", "难易程度", "目标数", "difficulty_dist.png")
        md.append(_md_img(p, "难易分布"))

    # ── 保存 MD ───────────────────────────────────────────────
    md_path = os.path.join(SAVE_DIR, "dataset_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"\n报告已生成: {md_path}")
    print(f"图片: {len(df_img)} | 目标: {len(df_obj)} | 类别: {df_obj['class'].nunique() if not df_obj.empty else 0}")


if __name__ == "__main__":
    run_analysis()
