# LabelU rectTool/tagTool 合并复制工具

这个工具按 `inner_id` 选择来源样本和目标范围，把来源样本的工具结果复制到目标样本。

默认模式是 `both`，同时复制：

- `rectTool`
- `tagTool`

也可以只复制其中一个：

- `--mode rect`
- `--mode tag`

## 安全行为

- 不提交 `state`，不会主动改动样本标记状态。
- 保留目标样本原始 `data` 的其它字段，只替换 `data.result`。
- 目标范围包含来源 `inner_id` 时会自动跳过来源样本。
- 提交前会把目标样本原文备份到 `outputs/*backup*.jsonl`。
- 复制 `rectTool` 时会补齐 `width/height/rotate`。

## 配置 token

推荐用环境变量：

```powershell
$env:LABELU_TOKEN="你的token"
```

也可以命令行传：

```powershell
python labelu_tool_unify.py --token 你的token
```

## 默认同时复制

```powershell
python labelu_tool_unify.py
```

临时指定范围：

```powershell
python labelu_tool_unify.py --task-id 167 --source-inner-id 361 --start-inner-id 361 --end-inner-id 369
```

## 只复制 rectTool

```powershell
python labelu_tool_unify.py --mode rect
```

## 只复制 tagTool

```powershell
python labelu_tool_unify.py --mode tag
```

## 只预览

```powershell
python labelu_tool_unify.py --dry-run
```

确认预览输出的 `inner_id`、`sample_id`、`rect_count`、`tag_count` 都符合预期后，再去掉 `--dry-run` 执行。

## 限制查找页码

默认会从 `page_start` 开始一直查到找到目标 `inner_id` 或列表结束。可以限制查找页码范围：

```powershell
python labelu_tool_unify.py --page-start 30 --page-end 40 --dry-run
```

如果 `page_end` 不填，表示不限制结束页。
