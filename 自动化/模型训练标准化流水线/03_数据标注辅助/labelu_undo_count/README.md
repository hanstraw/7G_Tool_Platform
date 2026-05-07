# LabelU 未完成样本统计脚本

本脚本用于统计LabelU指定任务中“未完成”的样本数量，并在脚本结束后自动生成一份 CSV。

CSV 文件名格式：

```text
task_任务ID_undo_count_时间.csv
```

例如：

```text
task_148_undo_count_20260424_181530.csv
```

## 快速使用

使用 Python 3.9+，先安装依赖：

```bash
pip install requests pyyaml
```

然后修改 [config.yaml]里的这几个值：

- `base_url`：你的 LabelU 地址
- `token`：可访问任务接口的 token，不要带 `Bearer `
- `target.task_id`：要统计的任务 ID

运行：

```bash
python count_undo.py
```

## 常用命令

临时指定任务 ID：

```bash
python count_undo.py --task-id 200
```

临时指定已完成状态：

```bash
python count_undo.py --finished-states DONE SKIPPED SKIP
```

临时指定输出目录：

```bash
python count_undo.py --output-dir reports
```

## 输出说明

脚本会生成 UTF-8 BOM 编码的 CSV，便于直接用 Excel 打开。

CSV 列说明：

- `task_id`：任务 ID
- `page`：页码
- `remaining_count`：当前页剩余数量

说明：

- 只输出剩余数量大于 0 的页码
- `page` 按你传入的 `page-size` 计算
- 脚本内部请求接口时固定按 100 条一页拉取
- “已标记”状态如果标签数量为 0，也会纳入检索

未完成的判断逻辑：

- 在 `finished_states` 里的状态，视为已完成
- 其他状态都视为未完成
