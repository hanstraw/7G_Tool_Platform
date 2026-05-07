# LabelU rectTool 统一化工具

这个工具用于把某个样本的 `rectTool` 标框复制到同一任务内一段 `inner_id` 范围的样本中。目标样本原有的 `tagTool` 全局标签和其它结果会保留，只替换或新增 `rectTool`。

默认会直接提交 PATCH，但不会在 payload 里写 `state`，所以不会主动改动样本标记状态。只想预览时加 `--dry-run`。

## 安装依赖

```bash
pip install requests pyyaml
```

## 配置

修改 [config.yaml]：

- `base_url`：LabelU 服务地址
- `target.task_id`：任务 ID
- `target.source_inner_id`：复制来源样本的 `inner_id`
- `target.target_inner_id_start` / `target.target_inner_id_end`：目标 `inner_id` 范围，包含起止值
- `target.rect_tool_name`：标框工具名，默认 `recttool`

推荐在 PowerShell 里设置 token：

```powershell
$env:LABELU_TOKEN="你的token"
```

也可以临时通过命令行传：

```bash
python labelu_recttool_unify.py --token 你的token
```

## 直接提交

```bash
python labelu_recttool_unify.py
```

临时指定任务和范围：

```bash
python labelu_recttool_unify.py --task-id 167 --source-inner-id 68 --start-inner-id 68 --end-inner-id 129
```

## 只预览

```bash
python labelu_recttool_unify.py --dry-run
```

## 行为说明

- 命令里的来源和范围都是 `inner_id`，脚本会自动映射到接口需要的 `sample_id`。
- 来源样本通过 `GET /api/v1/tasks/{task_id}/samples/{sample_id}` 读取完整内容。
- 目标样本也会逐个读取完整内容，再把来源 `rectTool` 写入目标 `data.result`。
- PATCH 地址为 `/api/v1/tasks/{task_id}/samples/{sample_id}?sample_id={sample_id}`。
- PATCH payload 会保留目标样本原始 `data` 的其它字段，只替换 `data.result`，并写入 `annotated_count`，不包含 `state`。
- 每个样本提交前会先把原始样本写入 `outputs/*backup*.jsonl`，方便回滚排查。
- `annotated_count` 按复制后的 `rectTool.result` 数量写入。
- 如果目标范围包含来源 `inner_id`，脚本会自动跳过来源样本。
- 默认会重新生成 `rectTool.result` 中每个标框的 `id`；如需完全保留来源 id，加 `--keep-rect-ids`。
- 查找 `inner_id` 时会从列表接口的 `page=0` 开始分页扫描；如果你的环境从 `page=1` 开始，可以加 `--page-start 1`。
- 每次运行会在 `outputs` 目录生成 CSV 报告。
