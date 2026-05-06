# Data Directory

该目录用于存放工具平台运行过程中的数据文件，前后端都可围绕这里的结构进行读写。

## 目录结构

- `configs/`
  - `environments.json`: 环境配置（LabelU、SSH 等）
  - `tools.json`: 工具注册清单（工具定义、参数 schema、执行入口）
- `plugins/`
  - 插件安装目录与运行入口
- `tasks/`
  - 任务状态与执行元数据（可按天分片）
- `logs/`
  - 任务执行日志（stdout/stderr）
- `artifacts/`
  - 任务产物（中间文件、导出文件、报告）
- `reports/`
  - 业务报告、验收清单等导出文本
- `db/`
  - 预留给 SQLite / DuckDB 等本地数据库文件

## 约束建议

1. 配置类数据用 JSON，结构固定，便于版本管理。
2. `logs/`、`tasks/`、`uploads/`、`artifacts/`、`reports/`、`db/`、`plugins/` 默认视为运行时目录，不提交到 Git。
3. 任务与日志使用统一 `task_id` 关联。
