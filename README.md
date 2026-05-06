# 7G Tool Platform

这是一个用于统一承载脚本工具的工具平台工程，已按前后端分层整理。

## 工程结构

- `docs/`: 项目文档与规范说明
- `frontend/`: 前端页面（当前已完成 MVP 原型）
- `backend/`: 后端服务（当前为接口骨架）
- `data/`: 平台数据层（配置、插件、任务、日志、产物、数据库文件）

根目录只保留入口脚本、核心源码和说明文档；运行产物统一写入 `data/`，本地临时文件通过 `.gitignore` 排除。

## 一键启动（推荐）

在 `7G_Tool_Platform` 目录执行：

```bash
python start_platform.py
```

会自动完成：

1. 启动后端服务（`127.0.0.1:8787`）
2. 启动前端静态服务（`127.0.0.1:5500`）
3. 自动打开浏览器进入前端页面

按 `Ctrl + C` 可同时关闭前后端。

## 手动启动（可选）

如果你需要分开排查，也可以手动分别启动前后端。

## 后端运行

在项目目录执行：

```bash
python backend/main.py
```

健康检查地址：

- `http://127.0.0.1:8787/api/health`
- `http://127.0.0.1:8787/api/environments`
- `http://127.0.0.1:8787/api/tools`

## 已接入工具（第一个）

- `labelu-json-to-voc-xml`
  - 脚本：`7G_Tool_Platform/backend/tools/labelu_json_to_voc_xml.py`（平台内置副本）
  - 前端可填写参数：`input_json`、`output_dir`、`folder`
  - 通过后端接口执行：`POST /api/tools/{tool_id}/run`

- `labelu-task-create`
  - 脚本：`7G_Tool_Platform/backend/tools/labelu_task_create.py`（平台内置副本）
  - 前端可填写参数：`base_url`、`username`、`password`、`task_name`、`media_type` 等
  - 功能：登录 LabelU 并创建任务

## 下一步接入

1. 将工具列表从前端静态数据切换为后端 `GET /api/tools`。
2. 为每个脚本定义参数 schema，并在前端渲染动态表单。
3. 实现 `POST /api/tools/{tool_id}/run` 调用本地脚本执行。
4. 增加执行日志与任务状态查询。

## 数据层说明

已预置 `data/configs/environments.json` 与 `data/configs/tools.json`，后续你新增工具和环境时可直接写入这两个文件，便于平台统一读取。

## 相关文档

- 项目全量现状说明：`docs/PROJECT_FULL_STATUS.md`
- 插件编写规范：`docs/PLUGIN_AUTHORING.md`
