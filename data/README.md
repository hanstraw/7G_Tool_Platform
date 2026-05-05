# Data Directory

该目录用于存放工具平台运行过程中的数据文件，前后端都可围绕这里的结构进行读写。

## 目录结构

- `configs/`
  - `environments.json`: 环境配置（LabelU、SSH 等）
  - `tools.json`: 工具注册清单（工具定义、参数 schema、执行入口）
- `tasks/`
  - 任务状态与执行元数据（可按天分片）
- `logs/`
  - 任务执行日志（stdout/stderr）
- `artifacts/`
  - 任务产物（中间文件、导出文件、报告）
- `db/`
  - 预留给 SQLite / DuckDB 等本地数据库文件

## 约束建议

1. 配置类数据用 JSON，结构固定，便于版本管理。
2. 大日志和大产物不入 Git，可按需加入 `.gitignore`。
3. 任务与日志使用统一 `task_id` 关联。
