# LabelU YOLOv11s 预标注

使用本地 YOLOv11s 模型对图片进行目标检测，生成 LabelU 可导入的预标注 JSON 文件。

与 `labelu_vlm_preannotate` 类似，但不依赖远程大模型 API，而是使用本地 YOLO 模型推理，速度更快，无需网络。

## 目录说明

```text
labelu_yolo_preannotate/
  config.yaml                 模型、路径、标签配置
  preannotate.py              预标注主脚本
  requirements.txt            依赖列表
  output/                     运行后生成的结果目录
```

## 安装依赖

```powershell
pip install -r requirements.txt
```

## 配置

编辑 `config.yaml`：

### 1. 图片目录

```yaml
paths:
  image_dir: ../data
```

### 2. 模型权重

```yaml
model:
  weights: ../best0430.pt
  confidence: 0.25
  iou: 0.45
  imgsz: 1920
  device: 0   
```

### 3. 类别映射

根据你的模型训练时 `data.yaml` 中 `names` 的顺序修改：

```yaml
class_mapping:
  0: object_basket
  1: object_bucket
  2: object_cabinet
  3: object_chair
  4: object_plasticbasket
  5: object_table
  6: streetVendor_catering
  7: streetVendor_clother
  8: streetVendor_fruit
  9: streetVendor_other
  10: streetVendor_vegetablet
```

### 4. LabelU 配置

```yaml
labelu:
  task_id: 1
  upload_subdir: images_only
  media_folder: /root/.local/share/labelu/media
```

## 运行

```powershell
cd labelu_yolo_preannotate
python .\preannotate.py
```

### 限制处理数量

```powershell
python .\preannotate.py --limit 10
```

### 从头重跑

```powershell
python .\preannotate.py --restart
```

或在 `config.yaml` 中设置：

```yaml
run:
  overwrite_checkpoint: true
```

## 中断后继续

直接再运行一次，已完成的图片会自动跳过：

```powershell
python .\preannotate.py
```

## 输出

结果在 `output/` 目录下，文件名类似：

```text
labelu_yolo_1_best0430.json
```

这个 JSON 可以直接导入 LabelU 做预标注。

## 与 VLM 版本的区别

| 特性 | VLM 版本 | YOLO 版本 |
|------|----------|-----------|
| 推理方式 | 远程大模型 API | 本地 YOLO 模型 |
| 速度 | 较慢（取决于网络和模型） | 很快（本地推理） |
| 全局标签 | 支持 | 不支持（只拉框） |
| 依赖 | requests | ultralytics |
| 并发 | 支持多线程 | 单线程（YOLO 已足够快） |
| 网络 | 需要 | 不需要 |
