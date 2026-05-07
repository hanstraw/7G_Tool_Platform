import os
import sys
import cv2
import json
import time
import threading
import numpy as np

from ctypes import cdll, byref, c_int, c_ubyte, c_float, c_char_p, c_void_p, c_uint32, c_bool, Structure, POINTER, c_uint8, cast, pointer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evaluation_utils import (
    Detection,
    SIZE_BINS,
    SIZE_BIN_DESC,
    _empty_stats,
    attach_scene_attrs,
    get_cpu_memory_mb,
    load_dataset_from_yaml,
    load_yolo_labels,
    match_detections_grouped,
    summarize_metrics,
    summarize_scene_metrics,
    summarize_size_metrics,
)

# ── 评估配置 ──────────────────────────────────────────────────
EVAL_DATA_PATH = "./data/test.yaml"
EVAL_XML_DIR   = "./data/labels/test"          # VOC XML 目录, 留空则跳过场景分组
EVAL_SAVE_DIR  = "./results_edge"
EVAL_IOU_THRES = 0.5
EVAL_CONF_THRES = 0.35
MODEL_PATH     = "./model/output_rknn"
RESULT_SAVE ="./results/"
# ─────────────────────────────────────────────────────────────


def write_txt_report(save_dir, summary, thresholds=None, scene_summary=None, size_summary=None):
    os.makedirs(save_dir, exist_ok=True)
    report_path = os.path.join(save_dir, 'evaluation_report.txt')
    NL = '\n'
    SEP = '-' * 60 + NL

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('YOLOv11 边缘评估报告' + NL)
        f.write(SEP)

        if thresholds:
            f.write('【评估配置】' + NL)
            for k, v in thresholds.items():
                f.write(f'  {k}: {v}' + NL)
            f.write(NL)

        f.write('【全局指标】' + NL)
        f.write(f'  评估图片数  : {summary["images"]}' + NL)
        f.write(f'  总耗时      : {summary["time_sec"]:.2f}s' + NL)
        f.write(f'  平均推理耗时: {summary["speed_avg_ms"]:.2f}ms/张' + NL)
        f.write(f'  mAP50       : {summary["map50"]:.4f}' + NL)
        f.write(f'  mAP50-95    : {summary["map5095"]:.4f}' + NL)
        f.write(f'  整体精确率  : {summary["overall_precision"]:.4f}' + NL)
        f.write(f'  整体召回率  : {summary["overall_recall"]:.4f}' + NL)
        f.write(f'  整体F1      : {summary["overall_f1"]:.4f}' + NL)
        if summary.get('cpu_memory_mb'):
            f.write(f'  CPU内存     : {summary["cpu_memory_mb"]:.1f}MB' + NL)
        for k, v in summary.get('extra_speed_metrics', {}).items():
            f.write(f'  {k}: {v:.2f}' + NL)
        f.write(NL)

        f.write('【各类别指标】' + NL)
        f.write(f'  {"类别":<30} {"标签数":>6} {"TP":>6} {"FP":>6} {"FN":>6} {"精确率":>8} {"召回率":>8} {"F1":>8} {"AP50":>8}' + NL)
        f.write('  ' + '-' * 90 + NL)
        for row in summary['per_class_rows']:
            f.write(
                f'  {row["name"]:<30} {row["labels"]:>6} {row["tp"]:>6} {row["fp"]:>6} {row["fn"]:>6}'
                f' {row["precision"]:>8.4f} {row["recall"]:>8.4f} {row["f1"]:>8.4f} {row["ap50"]:>8.4f}' + NL
            )
        f.write(NL)

        if size_summary:
            f.write('【尺寸分档指标】  (r = 目标面积 / 图像面积)' + NL)
            for bin_name, bin_data in size_summary.items():
                desc = SIZE_BIN_DESC.get(bin_name, '')
                f.write(f'  [{bin_name}]  {desc}  mAP50={bin_data["map50"]:.4f}' + NL)
                f.write(f'  {"类别":<30} {"精确率":>8} {"召回率":>8} {"F1":>8}' + NL)
                for cls in bin_data['per_class']:
                    f.write(f'  {cls["name"]:<30} {cls["precision"]:>8.4f} {cls["recall"]:>8.4f} {cls["f1"]:>8.4f}' + NL)
                f.write(NL)

        if scene_summary:
            f.write('【场景维度指标】' + NL)
            for field_key, val_dict in scene_summary.items():
                f.write(f'  == {field_key} ==' + NL)
                for val, val_data in val_dict.items():
                    f.write(f'  [{val}]  mAP50={val_data["map50"]:.4f}' + NL)
                    f.write(f'  {"类别":<30} {"精确率":>8} {"召回率":>8} {"F1":>8}' + NL)
                    for cls in val_data['per_class']:
                        f.write(f'  {cls["name"]:<30} {cls["precision"]:>8.4f} {cls["recall"]:>8.4f} {cls["f1"]:>8.4f}' + NL)
                    f.write(NL)

    return report_path

class DecodeDataRgb(Structure):
    """ creates a struct to match decode_data_st_t in c lib """
    _fields_ = [
        ('width', c_int),
        ('height', c_int),
        ('rgb_len', c_int),
        ('rgb_buf', POINTER(c_uint8)),
    ]
    def __str__(self):
        result = f'rgb_len:{self.rgb_len},width:{self.width},height:{self.height},'
        return result

class AILib:
    def __init__(self):
        self.ai_lib = cdll.LoadLibrary("/usr/lib/librknnx_api.so.3.4")
        # 1)creat_rknn_model_engine 函数说明
        # 输出
        self.ai_lib.creat_rknn_model_engine.restype = c_void_p
        self.ai_lib.creat_rknn_model_engine.argtypes = [c_char_p, c_float]

        # 2)init_rknn_model_engine 函数说明
        self.ai_lib.init_rknn_model_engine.restype = c_int
        self.ai_lib.init_rknn_model_engine.argtypes = [c_void_p]

        # 3) RknnRet delete_rknn_model_engine(rknn_ai ** rknnEngine); 函数说明
        self.ai_lib.delete_rknn_model_engine.restype = c_int
        self.ai_lib.delete_rknn_model_engine.argtypes = [POINTER(c_void_p)]

        # 4）char* rknn_model_engine_inference(rknn_ai* rknnEngine , uint8_t* imageBuf, uint32_t imageBufSize,
        # char* imageBufType,char* taskID,int w,int h,decode_data_st_t* decode_data) 函数说明
        self.ai_lib.rknn_model_engine_inference.restype = c_char_p
        self.ai_lib.rknn_model_engine_inference.argtypes = [c_void_p, c_char_p, c_uint32, c_char_p, c_char_p, c_int, c_int]

        # 5)  char* rknn_track_model_engine_inference(rknn_ai* rknnEngine , uint8_t* imageBuf, uint32_t imageBufSize,
        #  const char* imageBufType,const char* taskID,int width,int height,const char* detectResult,decode_data_st_t *decode_data=nullptr);
        self.ai_lib.rknn_track_model_engine_inference.restype = c_char_p
        self.ai_lib.rknn_track_model_engine_inference.argtypes = [c_void_p, c_char_p, c_uint32, c_char_p, c_char_p, c_int, c_int, c_char_p]

        # 6)RknnRet rknnx_get_device_info(char* deviceType ,char* filePath);
        self.ai_lib.rknnx_get_device_info.restype = c_int
        self.ai_lib.rknnx_get_device_info.argtypes = [c_char_p, c_char_p]

        # 7)char* rknn_model_engine_inference_batch(rknn_ai* rknnEngine ,decode_data_st_t** decode_data_vec,int batch, const char* imageBufType,const char* taskID);
        self.ai_lib.rknn_model_engine_inference_batch.restype = c_char_p
        self.ai_lib.rknn_model_engine_inference_batch.argtypes = [c_void_p, POINTER(POINTER(DecodeDataRgb)), c_int, c_char_p, c_char_p]

        # 识别线程列表
        self.thread_list = []
        self.modelEngPidList = []

    # 创建模型识别引擎
    def create_model_engine(self, modelPath, threshold, modelEngPidList):
        modelEngPid1 = c_void_p(self.ai_lib.creat_rknn_model_engine(modelPath.encode(), threshold))
        ret = self.ai_lib.init_rknn_model_engine(modelEngPid1)
        if ret < 0:
            print("init rknn model error")
        else:
            modelEngPidList.append(modelEngPid1)
            print("modelEngPid1:", modelEngPid1)

    #
    def delete_model_engine(self, modelEngPidList):
        # 3)释放识别引擎 delete_rknn_model_engine 函数
        # 说明
        for engIndex in range(len(modelEngPidList)):
            ret = self.ai_lib.delete_rknn_model_engine(byref(modelEngPidList[engIndex]))
            if ret < 0:
                print("delete rknn model error:,", modelEngPidList[engIndex])
            else:
                print("delete rknn model success:", modelEngPidList[engIndex])

    def create_camera_thread(self, cameraIndex, modelEngPidList):
        my_thread = threading.Thread(target=self.image_detection, args=(cameraIndex, modelEngPidList))
        my_thread.start()
        self.thread_list.append(my_thread)

    def load_image_to_struct(self, img):
        height, width, _ = img.shape

        # Use numpy's ctypes interface to create the buffer directly
        img_flat = img.ravel()  # This flattens the array without copying
        rgb_buf = img_flat.ctypes.data_as(POINTER(c_uint8))

        print("load_image_to_struct len img_flat:", img_flat.size)

        decode_data = DecodeDataRgb()
        decode_data.width = width
        decode_data.height = height
        decode_data.rgb_len = img_flat.size
        decode_data.rgb_buf = rgb_buf
        print("rgb_buf:", rgb_buf)

        return decode_data

    def generate_voc_xml(self, image_filename, image_path, image_data, xml_path, annotations):
        """Generate VOC format XML file"""
        import xml.etree.ElementTree as ET
        
        height, width, _ = image_data.shape
        
        root = ET.Element("annotation")
        
        folder = ET.SubElement(root, "folder")
        folder.text = "images"  # 根据你提供的示例
        
        filename = ET.SubElement(root, "filename")
        filename.text = image_filename
        
        path = ET.SubElement(root, "path")
        path.text = image_path
        
        source = ET.SubElement(root, "source")
        database = ET.SubElement(source, "database")
        database.text = "Unknown"
        
        size = ET.SubElement(root, "size")
        width_elem = ET.SubElement(size, "width")
        width_elem.text = str(width)
        
        height_elem = ET.SubElement(size, "height")
        height_elem.text = str(height)
        
        depth = ET.SubElement(size, "depth")
        depth.text = "3"
        
        segmented = ET.SubElement(root, "segmented")
        segmented.text = "0"
        
        for item in annotations:
            object_elem = ET.SubElement(root, "object")
            
            name = ET.SubElement(object_elem, "name")
            name.text = item["className"]
            
            pose = ET.SubElement(object_elem, "pose")
            pose.text = "Unspecified"
            
            truncated = ET.SubElement(object_elem, "truncated")
            truncated.text = "0"
            
            difficult = ET.SubElement(object_elem, "difficult")
            difficult.text = "0"
            
            bndbox = ET.SubElement(object_elem, "bndbox")
            
            xmin = ET.SubElement(bndbox, "xmin")
            xmin.text = str(round(item["X1"]))
            
            ymin = ET.SubElement(bndbox, "ymin")
            ymin.text = str(round(item["Y1"]))
            
            xmax = ET.SubElement(bndbox, "xmax")
            xmax.text = str(round(item["X2"]))
            
            ymax = ET.SubElement(bndbox, "ymax")
            ymax.text = str(round(item["Y2"]))
            
            # 如果需要的话，可以添加相似度信息
            # similarity = ET.SubElement(object_elem, "similarity")
            # similarity.text = str(item["similarity"])
        
        tree = ET.ElementTree(root)
        tree.write(xml_path)

    def save_cropped_images(self, image, annotations, base_filename, output_folder):
        """根据坐标裁剪小图并保存"""
        for idx, item in enumerate(annotations):
            x1 = round(item["X1"])
            y1 = round(item["Y1"])
            x2 = round(item["X2"])
            y2 = round(item["Y2"])
            
            # 确保坐标在图像范围内
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(image.shape[1], x2)
            y2 = min(image.shape[0], y2)
            
            if x1 >= x2 or y1 >= y2:
                continue  # 跳过无效的坐标
            
            # 裁剪图像
            cropped_img = image[y1:y2, x1:x2]
            
            # 生成文件名: 原文件名_类别_序号_坐标.jpg
            filename = f"{base_filename}_{item['className']}_{idx+1}_{x1}_{y1}_{x2}_{y2}.jpg"
            
            # 保存裁剪的图像
            save_path = os.path.join(output_folder, filename)
            cv2.imwrite(save_path, cropped_img)
            print(f"Saved cropped image: {save_path}")

    def image_detection(self, cameraIndex, modelEngPidList):
        count = 0
        batch_size = 16  # 设置批次大小为 8
        garbage_street_scattered_folder_path = RESULT_SAVE
        files = os.listdir(garbage_street_scattered_folder_path)
        files = [f for f in files if f.lower().endswith(('.jpg', '.jpeg'))]  # 筛选出图片文件

        output_folder = "./output"  # 指定保存结果的文件夹
        os.makedirs(output_folder, exist_ok=True)  # 确保文件夹存在
        xml_output_folder = "./outputxml"  # 指定保存XML的文件夹
        os.makedirs(xml_output_folder, exist_ok=True)  # 确保文件夹存在
        cropped_output_folder = "./cropped_images"  # 指定保存裁剪小图的文件夹
        os.makedirs(cropped_output_folder, exist_ok=True)  # 确保文件夹存在

        # 分批处理图片
        for i in range(0, len(files), batch_size):
            batch_files = files[i:i + batch_size]
            decodeList = []
            matList = []
            for filename in batch_files:
                file_path = os.path.join(garbage_street_scattered_folder_path, filename)
                print("Processing image:", file_path)
                img1 = cv2.imread(file_path)
                image1 = self.load_image_to_struct(img1)
                decodeList.append(image1)
                matList.append(img1)

            # 批量推理
            decode_data_array = (POINTER(DecodeDataRgb) * len(decodeList))(*(pointer(decode) for decode in decodeList))
            print("rknn_model_engine_inference_batch============")
            result = self.ai_lib.rknn_model_engine_inference_batch(
                modelEngPidList[0], decode_data_array, len(decodeList), "MAT".encode(), "task".encode())
            if result is not None:
                resultData = json.loads(c_char_p(result).value)
                print('resultData', resultData)
                imageObjs = resultData["imageObjs"]
                for idx, imageObj in enumerate(imageObjs):
                    image = matList[idx]
                    annotations = imageObj["alarmList"]
                    if not annotations:
                        continue
                    
                    # 绘制检测框
                    # for item in annotations:
                    #     newX1 = round(item["X1"])
                    #     newY1 = round(item["Y1"])
                    #     newX2 = round(item["X2"])
                    #     newY2 = round(item["Y2"])
                    #     image = cv2.rectangle(image, (newX1, newY1), (newX2, newY2), (255, 0, 0), 2)
                    #     className = item["className"]
                    #     similarity = round(item["similarity"], 2)
                    #     information = f"{className} {similarity}"
                    #     image = cv2.putText(image, information, (newX1 + 10, newY1), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 0, 0), 2)

                    # 获取原文件名（不包含扩展名）
                    original_filename = os.path.splitext(batch_files[idx])[0]
                    
                    # 指定保存路径，使用原始文件名
                    save_img_path = os.path.join(output_folder, f"{original_filename}_result.jpg")
                    save_xml_path = os.path.join(xml_output_folder, f"{original_filename}.xml")
                    
                    # cv2.imwrite(save_img_path, image)  # 保存图像文件
                    
                    # 生成VOC格式XML文件
                    if annotations:
                        img_path = os.path.join(garbage_street_scattered_folder_path, batch_files[idx])
                        self.generate_voc_xml(batch_files[idx], img_path, image, save_xml_path, annotations)
                        # 保存裁剪的小图
                        self.save_cropped_images(image, annotations, original_filename, cropped_output_folder)
                    
            count += 1
            time.sleep(3)
            if count == 1000:
                break


# ---------------------------------------------------------------------------------------
def evaluate():
    """基于边缘推理结果生成评估报告, 与云端报告格式一致."""
    os.makedirs(EVAL_SAVE_DIR, exist_ok=True)

    class_names, samples = load_dataset_from_yaml(EVAL_DATA_PATH)
    class_count = len(class_names)
    class_name_to_id = {name: i for i, name in enumerate(class_names)}

    if EVAL_XML_DIR and os.path.isdir(EVAL_XML_DIR):
        attach_scene_attrs(samples, EVAL_XML_DIR)

    ai_clib = AILib()
    ai_clib.create_model_engine(MODEL_PATH, c_float(EVAL_CONF_THRES), ai_clib.modelEngPidList)

    global_per_class = {cid: _empty_stats() for cid in range(class_count)}
    scene_accum: dict = {}
    size_accum = {b[0]: {cid: _empty_stats() for cid in range(class_count)} for b in SIZE_BINS}
    label_counts = np.zeros(class_count, dtype=int)
    inference_seconds = 0.0

    start_time = time.perf_counter()

    for sample in samples:
        image = cv2.imread(sample.image_path)
        if image is None:
            continue
        img_h, img_w = image.shape[:2]

        gt_boxes = load_yolo_labels(sample.label_path, img_w, img_h,
                                    class_names=class_names,
                                    xml_label_path=os.path.join(
                                        EVAL_XML_DIR,
                                        os.path.splitext(os.path.basename(sample.image_path))[0] + '.xml'
                                    ))
        for gt in gt_boxes:
            if 0 <= gt.class_id < class_count:
                label_counts[gt.class_id] += 1

        # 边缘推理 (C库期望RGB格式)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        decode_data = ai_clib.load_image_to_struct(image_rgb)
        decode_array = (POINTER(DecodeDataRgb) * 1)(pointer(decode_data))
        t0 = time.perf_counter()
        result = ai_clib.ai_lib.rknn_model_engine_inference_batch(
            ai_clib.modelEngPidList[0], decode_array, 1, "MAT".encode(), "eval".encode()
        )
        inference_seconds += time.perf_counter() - t0

        predictions = []
        if result is not None:
            result_data = json.loads(c_char_p(result).value)
            alarm_list = result_data.get("imageObjs", [{}])[0].get("alarmList", [])
            for item in alarm_list:
                cid = class_name_to_id.get(item.get("className", ""), -1)
                if cid < 0:
                    continue
                score = float(item.get("similarity", 1.0))
                if score < EVAL_CONF_THRES:
                    continue
                predictions.append(Detection(
                    x1=float(item["X1"]), y1=float(item["Y1"]),
                    x2=float(item["X2"]), y2=float(item["Y2"]),
                    class_id=cid, score=score,
                ))

        grouped = match_detections_grouped(
            predictions, gt_boxes, class_count,
            iou_threshold=EVAL_IOU_THRES,
            scene_attrs=sample.scene_attrs if sample.scene_attrs else None,
            img_w=img_w, img_h=img_h,
        )

        for cid in range(class_count):
            for k in ('tp', 'fp', 'fn'):
                global_per_class[cid][k] += grouped['per_class'][cid][k]
            global_per_class[cid]['scores'].extend(grouped['per_class'][cid]['scores'])
            global_per_class[cid]['matches'].extend(grouped['per_class'][cid]['matches'])

        for field_key, val_dict in grouped['scene'].items():
            if field_key not in scene_accum:
                scene_accum[field_key] = {}
            for val, pc in val_dict.items():
                if val not in scene_accum[field_key]:
                    scene_accum[field_key][val] = {cid: _empty_stats() for cid in range(class_count)}
                for cid in range(class_count):
                    for k in ('tp', 'fp', 'fn'):
                        scene_accum[field_key][val][cid][k] += pc[cid][k]
                    scene_accum[field_key][val][cid]['scores'].extend(pc[cid]['scores'])
                    scene_accum[field_key][val][cid]['matches'].extend(pc[cid]['matches'])

        for bin_name, pc in grouped['size'].items():
            for cid in range(class_count):
                for k in ('tp', 'fp', 'fn'):
                    size_accum[bin_name][cid][k] += pc[cid][k]
                size_accum[bin_name][cid]['scores'].extend(pc[cid]['scores'])
                size_accum[bin_name][cid]['matches'].extend(pc[cid]['matches'])

    ai_clib.delete_model_engine(ai_clib.modelEngPidList)

    total_time = time.perf_counter() - start_time
    cpu_mb = get_cpu_memory_mb()

    summary = summarize_metrics(
        class_names=class_names,
        per_class=global_per_class,
        label_counts=label_counts,
        total_images=len(samples),
        total_time_seconds=total_time,
        cpu_memory_mb=cpu_mb,
    )
    summary['extra_speed_metrics'] = {
        '平均推理耗时(ms/图)': (inference_seconds / max(len(samples), 1)) * 1000,
    }

    scene_summary = summarize_scene_metrics(scene_accum, class_names) if scene_accum else {}
    size_summary  = summarize_size_metrics(size_accum, class_names)

    report_path = write_txt_report(
        EVAL_SAVE_DIR, summary,
        thresholds={
            '模型路径':     MODEL_PATH,
            '数据集':       EVAL_DATA_PATH,
            '置信度阈值':   EVAL_CONF_THRES,
            'NMS IoU 阈值': EVAL_IOU_THRES,
            '推理后端':     '边缘 RKNN',
        },
        scene_summary=scene_summary,
        size_summary=size_summary,
    )

    print(f"图片: {len(samples)} | mAP50: {summary['map50']:.4f}")
    print(f"报告: {report_path}")


# ---------------------------------------------------------------------------------------
if __name__ == '__main__':
    evaluate()
