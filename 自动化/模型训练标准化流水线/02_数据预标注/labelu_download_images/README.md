# LabelU 任务图片下载工具

按任务 ID 下载 LabelU 任务里的所有图片到指定目录。

## 准备

```powershell
pip install requests pyyaml
$env:LABELU_TOKEN="你的token"
```

## 使用配置运行

修改 [config.yaml]：

- `target.task_id`：任务 ID
- `target.output_dir`：下载目录

然后运行：

```powershell
python download_images.py
```

## 命令行指定任务和路径

```powershell
python download_images.py --task-id 167 --output-dir C:\Users\Xiao\Desktop\task_167_images
```

## 下载部分页面

```powershell
python download_images.py --task-id 167 --output-dir C:\Users\Xiao\Desktop\task_167_images --page-start 0 --page-end 20
```

`page_end` 不传表示下载全部页面。

## 行为

- 使用 `/api/v1/tasks/{task_id}/samples` 分页获取样本。
- 使用样本里的 `file.url` 下载图片。
- 默认跳过已存在文件。
- 文件名冲突时默认加 `sample_id_` 前缀避免覆盖。
- 下载完成后在输出目录生成 `download_manifest_*.csv`。
