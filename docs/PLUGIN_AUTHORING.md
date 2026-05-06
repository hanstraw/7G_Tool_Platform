# 7G Tool Platform 插件编写规范（v1）

本文档用于统一多人协作下的插件开发方式。目标是：**开发者只需按规范准备插件目录，即可在平台导入并运行，无需改平台代码**。

## 1. 插件目录结构

每个插件一个目录，目录名建议与 `id` 一致：

```text
data/plugins/<plugin_id>/
  manifest.json
  main.py | main.js | run.ps1
  requirements.txt        # 可选（Python）
  package.json            # 可选（Node）
  README.md               # 可选（建议）
  ... 其他资源文件
```

必需文件：
- `manifest.json`
- 入口文件（由 `manifest.entry` 指定）

## 2. manifest.json 格式

### 2.1 必填字段

- `schema_version`: 当前固定 `"1.0"`
- `id`: 全局唯一插件 ID（建议小写英文+中划线）
- `name`: 展示名称
- `version`: 版本号（建议语义化，如 `1.0.0`）
- `group`: 分组名（用于前端分类）
- `desc`: 简介
- `runtime`: `python` / `node` / `shell`
- `entry`: 入口文件相对路径（相对于插件根目录）
- `params`: 参数定义数组

### 2.2 可选字段

- `status`: `ready` / `draft` / `offline`（默认 `ready`）
- `tags`: 标签数组
- `usage`: 使用说明文本
- `timeout_sec`: 执行超时秒数（默认 `1200`）
- `install`: 安装配置（可选）

### 2.3 params 字段规范

`params` 每一项支持：

- `key` (必填): 参数名，建议 snake_case
- `label` (可选): 前端展示名
- `type` (可选): `text` / `textarea` / `password` / `select` / `boolean` / `path` / `filelist`
- `required` (可选): `true/false`
- `default` (可选): 默认值
- `options` (可选): `select` 类型可选项数组
- `cli_arg` (可选): 命令行参数名（不带 `--`），默认把 `key` 的 `_` 转 `-`

> 平台会将参数转换为命令行参数传给脚本：`--<cli_arg> <value>`。

## 3. 可直接复制的模板

### 3.1 Python 插件模板

```json
{
  "schema_version": "1.0",
  "id": "demo-python-tool",
  "name": "示例 Python 工具",
  "version": "1.0.0",
  "group": "示例",
  "desc": "演示 Python 插件接入格式。",
  "runtime": "python",
  "entry": "main.py",
  "status": "ready",
  "tags": ["demo", "python"],
  "timeout_sec": 600,
  "params": [
    { "key": "input_path", "label": "输入路径", "type": "path", "required": true, "cli_arg": "input-path" },
    { "key": "output_path", "label": "输出路径", "type": "path", "required": true, "cli_arg": "output-path" },
    { "key": "overwrite", "label": "覆盖输出", "type": "boolean", "required": false, "default": "false", "cli_arg": "overwrite" }
  ]
}
```

`main.py` 示例：

```python
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-path", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    print(f"input={args.input_path}, output={args.output_path}, overwrite={args.overwrite}")


if __name__ == "__main__":
    main()
```

### 3.2 Node 插件模板

`runtime` 改为 `node`，`entry` 指向 `main.js`。平台执行命令为 `node <entry>`。

### 3.3 Shell 插件模板

`runtime` 改为 `shell`，建议入口用 `run.ps1`。平台执行命令为：

```powershell
powershell -ExecutionPolicy Bypass -File <entry>
```

## 4. 安装行为（可选）

平台导入插件时可自动安装依赖：

1) 若 `manifest.install.commands` 有定义，优先按顺序执行。  
2) 否则自动探测：
- 有 `requirements.txt` -> `python -m pip install -r requirements.txt`
- 有 `package.json` -> `npm install`

示例：

```json
"install": {
  "commands": [
    "python -m pip install -r requirements.txt"
  ]
}
```

## 5. 编写注意事项（强制建议）

- **ID 唯一**：`id` 冲突会导入失败（除非选择覆盖）。
- **入口必须存在**：`entry` 指向的文件必须在插件目录内。
- **参数命名稳定**：`key` 和 `cli_arg` 发布后尽量不要改，避免历史调用失效。
- **默认值类型统一为字符串**：便于前端与命令行一致处理。
- **路径参数优先用 `path`/`filelist`**：便于使用者理解。
- **脚本输出要可读**：关键步骤 `print` 出来，方便日志排查。
- **任务必须可重试**：失败后再次执行不应破坏数据。
- **长任务设置 `timeout_sec`**：避免无穷等待。

## 6. 常见错误与排查

- 导入报 `manifest 缺少必填字段`
  - 检查必填项是否完整、字段名是否拼写正确。
- 导入报 `entry 文件不存在`
  - 检查 `entry` 相对路径、文件名大小写。
- 运行报 `缺少必填参数`
  - 检查 `params.required=true` 的字段是否在前端填写。
- 运行超时
  - 增大 `timeout_sec`，或优化脚本执行逻辑。

## 7. 团队验收清单（提交插件前）

- [ ] 目录结构符合规范
- [ ] `manifest.json` 可被 JSON 解析
- [ ] 必填字段齐全
- [ ] 入口文件存在并可独立执行
- [ ] 必填参数均有处理
- [ ] 本地命令行执行成功一次
- [ ] 导入平台成功一次
- [ ] 平台运行成功并有日志

---

如需统一模板仓库，建议将本文档和最小示例插件一起打包给团队，作为“插件脚手架”使用。
