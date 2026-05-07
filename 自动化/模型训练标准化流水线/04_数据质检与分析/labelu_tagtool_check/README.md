# LabelU tagTool 完整性检查脚本

这个脚本用于扫描 LabelU 指定任务中已做完状态的样本，按每页 10 条检查两类问题：

- `DONE` 但缺 `tagTool` 内容：没有 `tagTool`、`tagTool.result` 不是列表，或标签数量少于配置要求
- `DONE` 但标框为 0：没有 `rectTool`、`rectTool.result` 不是列表，或标框数量少于配置要求
- `DONE` 但 `data.result.width/height` 小于等于 0

脚本结束后会自动生成一份 CSV。

## 快速使用

使用 Python 3.9+，先安装依赖：

```bash
pip install requests pyyaml
```

然后修改 [config.yaml] 里的几个值：

- `base_url`：你的 LabelU 地址
- `token`：可访问任务接口的 token，不要带 `Bearer `
- `target.task_id`：要检查的任务 ID
- `target.expected_tag_count`：期望的 `tagTool.result` 标签数量，默认 6；以后不是 6 时改这里即可
- `target.min_box_count`：最少需要的 `rectTool.result` 标框数量，默认 1

运行：

```bash
python labelu_tagtool_check.py
```

## 常用命令

临时指定任务 ID：

```bash
python labelu_tagtool_check.py --task-id 200
```

临时指定检查状态：

```bash
python labelu_tagtool_check.py --states DONE
```

临时指定期望标签数量：

```bash
python labelu_tagtool_check.py --expected-tag-count 6
```

临时指定最少标框数量：

```bash
python labelu_tagtool_check.py --min-box-count 1
```

临时指定输出目录：

```bash
python labelu_tagtool_check.py --output-dir reports
```

## CSV 列说明

- `task_id`：任务 ID
- `page`：页码，按每页 10 条计算，输出为接口页码 + 1
- `sample_id`：样本 ID
- `inner_id`：样本内部序号
- `state`：样本状态
- `filename`：文件名
- `file_url`：文件地址
- `issue_category`：问题大类，`tagtool_content_issue` 表示缺 `tagTool` 内容，`box_issue` 表示标框问题
- `issue_type`：问题类型
- `expected_tag_count`：期望标签数量
- `actual_tag_count`：实际标签数量
- `expected_box_count`：期望标框数量
- `actual_box_count`：实际标框数量
- `result_width`：`data.result.width`
- `result_height`：`data.result.height`
- `found_tag_tool_name`：实际找到的标签工具名
- `found_box_tool_name`：实际找到的标框工具名
- `detail`：问题说明
