# Backend

该目录用于放置工具平台后端服务（脚本注册、任务调度、执行日志、状态查询）。

## 规划接口（MVP）

- `GET /api/tools`：获取工具列表
- `POST /api/tools/{tool_id}/run`：执行某个工具
- `GET /api/tasks/{task_id}`：查询任务状态与日志

## 下一步

1. 选择后端框架（建议 FastAPI）。
2. 定义统一工具配置模型（名称、参数 schema、执行命令）。
3. 实现本地脚本执行器与日志流转。
