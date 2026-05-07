# LabelU 全局标签统一化工具

这个工具用于把某个样本的 `tagTool` 全局标签复制到同一任务内一段 `inner_id` 范围的样本中。目标样本原有的 `rectTool` 标框和其它结果会保留，只替换或新增 `tagTool`。

默认会直接提交 PATCH；如果只想预览，加 `--dry-run`。

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
- 默认不提交 `state`，不会主动改动样本标记状态；只有命令行显式传 `--state DONE` 时才会写状态。

不要把 token 写进脚本。推荐在 PowerShell 里设置环境变量：

```powershell
$env:LABELU_TOKEN="你的token"
```

也可以临时通过命令行传：

```bash
python labelu_tagtool_unify.py --token 你的token
```

## 直接提交

```bash
python labelu_tagtool_unify.py
```

临时指定任务和范围：

```bash
python labelu_tagtool_unify.py --task-id 148 --source-inner-id 7016 --start-inner-id 7017 --end-inner-id 7040
```

## 只预览

```bash
python labelu_tagtool_unify.py --dry-run
```

完整示例：

```bash
python labelu_tagtool_unify.py --task-id 148 --source-inner-id 7016 --start-inner-id 7017 --end-inner-id 7040
```

## 行为说明

- 来源样本通过 `GET /api/v1/tasks/{task_id}/samples/{sample_id}` 读取完整内容。
- 查找 `inner_id` 时会从列表接口的 `page=0` 开始分页扫描；如果你的环境从 `page=1` 开始，可以加 `--page-start 1`。
- 目标样本也会逐个读取完整内容，再把来源 `tagTool` 写入目标 `data.result`。
- PATCH payload 会保留目标样本原始 `data` 的其它字段，只替换 `data.result`。
- 每个样本提交前会先把原始样本写入 `outputs/*backup*.jsonl`，方便回滚排查。
- 如果目标范围包含来源 `inner_id`，脚本会自动跳过来源样本。
- PATCH 地址为 `/api/v1/tasks/{task_id}/samples/{sample_id}?sample_id={sample_id}`。
- 默认 PATCH payload 不包含 `state`，避免影响其他用户看到的标注状态。
- `annotated_count` 按目标样本 `rectTool.result` 数量写入；如果没有标框，则保留目标原 `annotated_count` 或写 0。
- 默认会重新生成 `tagTool.result` 中每条标签的 `id`；如需完全保留来源 id，加 `--keep-tag-ids`。
- 每次运行会在 `outputs` 目录生成 CSV 报告。
