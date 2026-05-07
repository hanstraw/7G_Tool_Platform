# LabelU 多模态大模型预标注

这个项目用于读取 `../images` 里的图片，调用多模态大模型生成 LabelU 可导入的预标注 JSON。

输出文件：

```text
output/labelu_任务ID_模型名称.json
```

如果同名 JSON 已经存在，脚本不会覆盖，会自动生成 `_1`、`_2` 这样的新文件名。本次实际输出文件名会记录在 `output/checkpoint.jsonl` 的 meta 行里，断点续跑会继续写同一个 JSON。

这个文件可作为 LabelU 的预标注 JSON 文件上传。

## 目录说明

```text
labelu_vlm_preannotate/
  config.yaml                 模型、路径、标签配置
  preannotate.py              预标注主脚本
  validate_labelu_json.py     输出格式校验脚本
  output/                     运行后生成的结果目录
```

## 安装依赖

```powershell
cd C:\Users\Xiao\Desktop\街道图片\labelu_vlm_preannotate
pip install -r requirements.txt
```

## 配置模型

编辑：

```text
config.yaml
```

主要字段：

```yaml
model:
  base_url: https://api.siliconflow.cn/v1
  api_key: sk-你的key
  model: Qwen/Qwen3.6-27B
  timeout_seconds: 300
  retries: 2
  stream: false
  enable_thinking: false
  thinking:
    type: disabled
  reasoning:
    effort: minimal
  thinking_budget: 128
  max_tokens: 1500
  coordinate_mode: auto
  request_image:
    width:
    height:
    quality: 90
```

LabelU 导入预标注需要 `url/folder/fileName/result` 字段。当前配置会自动生成：

```yaml
labelu:
  task_id: 163
  upload_subdir: images_only
  media_folder: /root/.local/share/labelu/media
```

`api_key` 直接填完整 key：

```yaml
api_key: sk-你的key
```

## 测试 1 张

```powershell
python .\preannotate.py --limit 1
python .\validate_labelu_json.py .\output\labelu_preannotations.json
```

## 正式运行

```powershell
python .\preannotate.py
```

运行中会持续打印进度，例如：

```text
图片目录: C:\Users\Xiao\Desktop\街道图片\images
输出文件: C:\Users\Xiao\Desktop\街道图片\labelu_vlm_preannotate\output\labelu_preannotations.json
总图片数: 159
已完成: 12
待处理: 147
模式: Qwen/Qwen3.6-27B
预标注进度:   8%|██▎                           | 12/159 [12:30<2:31:00, 61.6s/张]

[13/159] 开始: 1_000025_000125s.jpg
[13/159] 模型处理中: 1_000025_000125s.jpg
  - 编码图片: 1_000025_000125s.jpg
  - 图片编码完成: 0.10 MB base64
  - 发送模型请求: Qwen/Qwen3.6-27B，timeout=300s，attempt=1/3
  - 收到模型响应: HTTP 200，耗时 1m12s
  - 开始接收流式输出:
{"rects":[...],"tags":{...}}
  - 流式输出接收完成: 672 字符
  - 模型原始输出: {"rects":[...],"tags":{...}}
  - 解析模型 JSON: 672 字符
  - 模型 JSON 解析完成
  - 解析框数量: 3
    box 1: streetVendor_catering x=120, y=80, w=60, h=90, conf=0.82
  - 解析标签: sceneType=commercialStreet, lighting=normalDaylight, weather=sunny, quality=clear, angle=topView, source=cameraCapture
[13/159] 完成: 1_000025_000125s.jpg，框 3 个，本次 1 张，累计 13 张，耗时 1m31s，预计剩余 3h42m10s
```

框质量控制在 `config.yaml` 的 `run` 中配置：

```yaml
mode: global_tags_only

run:
  parallel: 4
  max_rects: 8
  min_confidence: 0.8
```

有两个模式：

```yaml
mode: global_tags_only
```

默认模式，只做全局标签，不拉框。输出里 `rectTool.result` 会是空数组。
这个模式的提示词只包含全局标签分类要求和全局标签候选值，不包含框标签、坐标格式、目标检测规则。

```yaml
mode: boxes_and_tags
```

拉框 + 全局标签。提示词参考了人工标注标准，但改成了模型可执行规则：摊贩主体优先、同一摊位一框、固定店铺不标、强光不等于摊贩、附属物默认少标。
这个模式每张图片只调用一次大模型，要求模型在同一次响应里同时返回 `rects` 和 `tags`，不会先拉框再单独调用一次做全局标签。

默认 `parallel: 4`，会同时处理 4 张图片。默认 `stream: false`，模型内容不再流式打印到终端，终端只显示提交、完成、失败和进度条。遇到 `429 Too Many Requests` 时脚本会等待后重试。

脚本会递归读取：

```text
../images
```

并生成：

```text
output/labelu_163_Qwen_Qwen3.5-4B.json
```

## 中断后继续

脚本支持断点续跑。

每成功处理一张图片，会立即写入：

```text
output/checkpoint.jsonl
output/labelu_preannotations.json
```

如果中途退出、断网、模型报错，下一次直接重新运行：

```powershell
python .\preannotate.py
```

已经完成的图片会自动跳过，从下一张继续。

## 从头重跑

如果要清空进度并从第一张重新开始：

```powershell
python .\preannotate.py --restart
```

## 校验结果

```powershell
python .\validate_labelu_json.py .\output\labelu_preannotations.json
```

看到类似输出即表示格式可用：

```text
OK: 159 records
```

## 修复已有预标注 JSON

如果旧文件缺少 `url` 或 `folder` 字段，运行：

```powershell
python .\fix_preannotation_json.py
```

脚本会先备份旧文件，再原地修复：

```text
output/labelu_163_Qwen_Qwen3.5-4B.json
```

## 上传到 LabelU

在 LabelU 上传数据时，把下面文件作为预标注 JSON 上传：

```text
C:\Users\Xiao\Desktop\街道图片\labelu_vlm_preannotate\output\labelu_163_Qwen_Qwen3.5-4B.json
```

预标注 JSON 结构参考：

https://opendatalab.github.io/labelU/schema/pre-annotation/json
提示词统一要求模型输出 `0.0-1.0` 比例坐标，脚本会转换成 LabelU 像素坐标。`coordinate_mode: auto` 会兼容模型偶尔输出 `0-1000` 或像素坐标的情况。

`request_image.width/height` 留空时会发送原始分辨率图片。填写数值时会缩放后发送，但最终仍输出原图尺寸的 LabelU 坐标。
