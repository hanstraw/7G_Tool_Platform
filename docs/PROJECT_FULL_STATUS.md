# 7G Tool Platform 项目全量现状说明

最后整理时间：2026-05-06

## 1. 文档目的

本文档用于把当前仓库的真实情况完整梳理清楚，覆盖以下几个维度：

1. 这个项目最初想解决什么问题。
2. 当前仓库里实际已经实现了什么。
3. 代码实现、历史运行结果、文档描述之间有哪些一致和不一致。
4. 当前项目能否直接使用，适合用于什么场景。
5. 后续继续推进时，优先级应该怎么排。

本文档以当前仓库代码、当前目录结构、现有配置文件、历史任务文件、历史日志文件为准，不以理想设计或口头预期为准。

## 2. 项目定位与原始需求

从 [README.md](/data/7G_Tool_Platform/README.md)、[backend/README.md](/data/7G_Tool_Platform/backend/README.md)、[docs/PLUGIN_AUTHORING.md](/data/7G_Tool_Platform/docs/PLUGIN_AUTHORING.md) 以及现有代码结构来看，这个项目的原始目标可以归纳为：

1. 做一个统一的“脚本工具平台”。
2. 让零散的本地脚本、数据处理脚本、标注辅助脚本、模型相关脚本通过一个统一界面被使用。
3. 让前端负责：
   - 展示工具列表
   - 按分组检索工具
   - 渲染参数表单
   - 发起执行
   - 查看执行结果、日志和产物
4. 让后端负责：
   - 提供工具列表接口
   - 接收执行请求
   - 把参数转成命令行
   - 异步执行插件脚本
   - 保存任务状态、日志、产物信息
5. 让插件机制负责：
   - 新工具按目录规范接入
   - 不改平台核心代码即可新增工具
   - 支持本地导入、ZIP 导入、Git 导入
6. 让数据目录负责：
   - 统一存放配置、插件、日志、任务、上传文件、执行产物、报告、数据库文件

也就是说，这不是一个单一脚本，而是一个“工具聚合平台”。

## 3. 当前项目的一句话结论

当前仓库不是“纯原型”，也不是“完整生产版”，而是一个已经能运行、已经跑过多轮任务、但仍存在明显版本断层和工程不一致的半成品平台。

更准确地说：

1. 前端可打开、可展示工具、可提交运行、可轮询任务、可查看输出和产物。
2. 后端可启动 HTTP 服务，具备工具查询、任务提交、任务查询、日志查询、产物下载、插件导入能力。
3. 插件执行链路已经成型，不再只是接口骨架。
4. `data/` 目录中保留了大量真实任务、日志、报告，证明这个平台已经被实际使用过。
5. 但是：
   - 当前代码和历史运行数据之间存在能力差异。
   - 文档有一部分已经过时。
   - 当前目录中的 `data/plugins/` 存在权限异常，影响当前仓库的可读性和可复现性。
   - 启动配置和前后端地址是硬编码的，不适合直接迁移部署。

## 4. 当前目录结构与职责

当前根目录已经整理为：

```text
7G_Tool_Platform/
  README.md
  __init__.py
  start_platform.py
  backend/
  frontend/
  data/
  docs/
```

各目录职责如下。

### 4.1 根目录

- `README.md`
  - 项目总说明。
- `start_platform.py`
  - 一键启动脚本。
- `__init__.py`
  - 目前基本无实际业务意义。

### 4.2 `backend/`

后端服务代码，包含：

- `main.py`
  - HTTP 服务入口。
- `storage.py`
  - 数据目录与任务、日志读写。
- `plugin_loader.py`
  - 插件清单读取。
- `plugin_installer.py`
  - 本地目录、ZIP、Git 插件导入。
- `plugin_runner.py`
  - 任务异步执行器。
- `manifest_schema.py`
  - 插件 manifest 规范化与校验。
- `tools/`
  - 平台内置脚本副本。

### 4.3 `frontend/`

静态前端页面，包含：

- `index.html`
  - 页面骨架。
- `app.js`
  - 页面逻辑、接口调用、弹窗、轮询、导入插件、环境配置。
- `styles.css`
  - 基础样式。

### 4.4 `data/`

运行态数据目录，当前包含：

- `configs/`
  - 配置文件。
- `plugins/`
  - 插件目录。
- `tasks/`
  - 任务状态 JSON。
- `logs/`
  - 任务日志。
- `uploads/`
  - 上传中间文件。
- `artifacts/`
  - 执行产物。
- `reports/`
  - 验收报告、业务报告。
- `db/`
  - 预留数据库目录。

### 4.5 `docs/`

文档目录，当前至少包含：

- `PLUGIN_AUTHORING.md`
  - 插件编写规范。

本次新增：

- `PROJECT_FULL_STATUS.md`
  - 本文档。

## 5. 启动方式与实际运行行为

### 5.1 设计意图

从 `README` 看，设计目标是：

1. 执行 `python start_platform.py`
2. 自动启动后端
3. 自动启动前端静态服务
4. 自动打开浏览器

### 5.2 当前实际实现

[start_platform.py](/data/7G_Tool_Platform/start_platform.py) 的当前行为是：

1. 在 `backend/` 下执行 `main.py`
2. 在 `frontend/` 下启动 `python -m http.server 5500 --bind 0.0.0.0`
3. 打印前后端地址
4. 休眠 1.2 秒后自动打开浏览器
5. 监控两个子进程
6. 任一子进程退出时整体停止

### 5.3 当前实现中的实际问题

1. `HOST` 被硬编码为 `192.168.54.120`
   - 后端健康检查 URL 和前端 URL 都基于这个 IP 拼接。
   - 这意味着代码天然依赖某个特定内网地址，不适合直接迁移。
2. `README` 里仍写的是 `127.0.0.1`
   - 文档与代码不一致。
3. 前端服务是 Python 自带静态服务器
   - 适合开发/内网演示，不适合严肃部署。
4. 没有健康检查等待机制
   - 只是固定 `sleep 1.2`，启动慢时可能打开页面过早。

## 6. 后端现状

### 6.1 后端是否只是“接口骨架”

不是。

[backend/README.md](/data/7G_Tool_Platform/backend/README.md) 仍写着“接口骨架”和“下一步选择 FastAPI”，但当前 [backend/main.py](/data/7G_Tool_Platform/backend/main.py) 已经实现了一个可工作的 HTTP 服务。

当前后端是：

- 基于 `http.server.BaseHTTPRequestHandler`
- 非 FastAPI
- 非 Flask
- 使用标准库 HTTPServer

也就是说，文档明显落后于代码现状。

### 6.2 当前后端提供的接口

根据 `backend/main.py`，当前实际接口有：

#### 基础接口

- `GET /api/health`
- `GET /api/environments`
- `GET /api/tools`
- `GET /api/tools/{tool_id}`

#### 执行与任务接口

- `POST /api/tools/{tool_id}/run`
- `GET /api/tasks/{task_id}`
- `GET /api/tasks/{task_id}/log`
- `GET /api/tasks/{task_id}/artifacts`
- `GET /api/tasks/{task_id}/artifacts/{index}?mode=inline|download`
- `GET /api/logs/{file_name}`

#### 插件导入接口

- `POST /api/plugins/register-local`
- `POST /api/plugins/upload`
- `POST /api/plugins/import-git`

### 6.3 当前后端架构特点

1. HTTP 服务是同步单进程的 `HTTPServer`
2. 插件执行是通过 `ThreadPoolExecutor` 异步提交
3. 任务状态落盘到 `data/tasks/*.json`
4. 日志落盘到 `data/logs/*.log`
5. 产物通过任务中的 `artifacts` 数组描述

### 6.4 当前后端优点

1. 依赖少，部署简单。
2. 不需要复杂框架就能完成基本执行链路。
3. 任务结果可持久化，后端重启后仍可通过任务文件查看历史状态。
4. 已支持插件导入，不只是静态配置。

### 6.5 当前后端限制

1. `HTTPServer` 不是高并发方案。
2. 没有统一异常模型。
3. 没有鉴权。
4. CORS 直接是 `*`。
5. 没有请求级权限控制。
6. 没有取消任务接口。
7. 没有任务列表接口。
8. 没有环境配置保存接口。
9. 没有真正的文件上传 API，前端插件导入只是提交“路径字符串”。

## 7. 插件机制现状

### 7.1 目标设计

[docs/PLUGIN_AUTHORING.md](/data/7G_Tool_Platform/docs/PLUGIN_AUTHORING.md) 描述的目标是：

1. 每个插件一个目录。
2. 用 `manifest.json` 描述元信息。
3. 通过 `runtime + entry + params` 驱动执行。
4. 支持 Python / Node / Shell。
5. 支持导入时自动安装依赖。

### 7.2 当前代码已实现能力

从 `plugin_loader.py`、`plugin_installer.py`、`plugin_runner.py`、`manifest_schema.py` 看，当前插件链已经具备：

1. 按 `data/plugins/<plugin_id>/manifest.json` 扫描插件。
2. 校验 manifest 必填字段。
3. 校验 `runtime` 是否属于 `python/node/shell`。
4. 校验入口文件是否存在。
5. 将参数定义规范化。
6. 根据参数类型构造命令行。
7. 支持自动安装依赖：
   - manifest 自定义 install.commands
   - `requirements.txt`
   - `package.json`
8. 支持三种导入方式：
   - 本地目录
   - ZIP 文件
   - Git 仓库

### 7.3 当前执行时的命令构造方式

`PluginRunner._build_command()` 的逻辑是：

1. `python` 运行时：`sys.executable entry`
2. `node` 运行时：`node entry`
3. `shell` 运行时：`powershell -ExecutionPolicy Bypass -File entry`
4. 对每个参数：
   - 若是 `boolean`
     - 只有值为 `true/1/yes/on` 时才追加 `--flag`
   - 否则：
     - 追加 `--cli-arg value`

### 7.4 当前产物识别方式

当前产物并不是后端主动扫描输出目录，而是依赖插件脚本在 `stdout` 中打印：

```text
[ARTIFACT] /path/to/file
```

后端通过 `_extract_artifacts()` 从标准输出中提取产物路径。

这意味着：

1. 插件作者必须主动遵守 `[ARTIFACT]` 约定。
2. 如果插件生成了文件但不打印 `[ARTIFACT]`，前端不会自动显示产物。

### 7.5 当前插件体系的现实问题

1. `data/plugins/` 当前目录存在权限异常
   - 当前工作区可以看到插件目录名，但无法读取目录内容。
   - 这会影响当前仓库的可维护性和可复现性。
2. `plugin_loader.list_plugins()` 的降级逻辑是：
   - 优先扫 `data/plugins/*/manifest.json`
   - 如果扫不到，再回退到 `data/configs/tools.json`
3. 这意味着：
   - 一旦 `data/plugins/` 因权限问题不可读
   - 当前实际可见工具可能退化到 `tools.json` 中定义的少量旧工具
4. 插件实际数量明显多于当前 `tools.json`
   - 这从历史任务与 `data/plugins/` 目录名能直接看出

## 8. 工具清单现状

### 8.1 代码内仍显式保留的内置工具

当前仓库 `backend/tools/` 下明确存在两个平台内置脚本副本：

1. [backend/tools/labelu_json_to_voc_xml.py](/data/7G_Tool_Platform/backend/tools/labelu_json_to_voc_xml.py)
2. [backend/tools/labelu_task_create.py](/data/7G_Tool_Platform/backend/tools/labelu_task_create.py)

这说明项目最初是从“少量内置工具”起步的。

### 8.2 `tools.json` 中的遗留工具定义

[data/configs/tools.json](/data/7G_Tool_Platform/data/configs/tools.json) 目前只定义了两个工具：

1. `labelu-json-to-voc-xml`
2. `labelu-task-create`

但这里有一个明显问题：

1. 这些参数项的 `type` 使用了 `string`
2. 而 `manifest_schema.py` 支持的参数类型是：
   - `text`
   - `textarea`
   - `password`
   - `select`
   - `boolean`
   - `path`
   - `filelist`

说明 `tools.json` 是旧格式遗留，不是当前 manifest 体系的正式格式。

### 8.3 从历史运行数据推断的真实插件范围

当前仓库历史数据中出现过的工具至少包括：

1. `alarm-daily-report`
2. `cn-name-to-en-project`
3. `filter-copy-no-gamma`
4. `filter-copy-no-thumbnail`
5. `image-xml-pair-check`
6. `labelu-delete`
7. `labelu-json-to-voc-xml`
8. `labelu-task-create`
9. `voc-dataset-analysis`
10. `voc-labelu-convert`
11. `voc-xml-add-global-attrs`
12. `voc-xml-add-size-from-image`
13. `voc-xml-fix-filename`
14. `voc-xml-invalid-size`
15. `voc-xml-label-count-report`
16. `voc-xml-remove-empty-objects`
17. `yolo-dataset-prepare`
18. `yolo-eval-gpu`
19. `yolo-eval-onnx`
20. `yolo-export-onnx`
21. `yolo-pre-annotate-labelu`

这说明历史运行过的平台能力明显比当前 `tools.json` 描述的要多。

## 9. 前端现状

### 9.1 当前前端是否只是原型页

也不是。

[frontend/index.html](/data/7G_Tool_Platform/frontend/index.html) + [frontend/app.js](/data/7G_Tool_Platform/frontend/app.js) 已经实现了完整的单页操作流程。

### 9.2 当前前端已具备的功能

1. 展示品牌头部、环境按钮、导入插件按钮。
2. 左侧按分组展示工具。
3. 中间支持搜索和状态筛选。
4. 中间卡片展示工具名称、描述、状态、版本。
5. 支持打开“使用说明”弹窗。
6. 支持根据参数定义渲染运行表单。
7. 支持提交运行请求。
8. 支持轮询任务状态。
9. 支持展示标准输出、错误输出、日志文件名、退出码。
10. 支持展示产物列表，并提供查看/下载链接。
11. 支持导入插件：
   - 本地目录
   - ZIP 路径
   - Git 仓库
12. 支持一个“环境配置”弹窗。

### 9.3 当前前端的真实限制

1. API 地址硬编码为：
   - `http://192.168.54.120:8787`
2. 这与 `README` 中的 `127.0.0.1` 描述不一致。
3. 环境配置只保存在浏览器 `localStorage`
   - key 是 `tool_platform_env_config`
4. 也就是说：
   - 环境配置不会保存回后端
   - 不会写回 `data/configs/environments.json`
   - 前端环境配置与后端环境接口是脱节的
5. 插件导入并不是浏览器上传 ZIP 文件
   - 只是把本机路径字符串发给后端
   - 这说明前端默认假设“浏览器和后端处在同一台可访问同一路径的机器或内网环境”
6. 没有登录、没有用户体系、没有权限隔离

### 9.4 当前 UI 与项目定位的匹配度

从功能上看，前端已经适合：

1. 内网工具平台
2. 团队内部运维/数据处理工具集合页
3. 面向熟悉路径、熟悉脚本的操作人员

但还不适合：

1. 外部用户产品化交付
2. 互联网公开服务
3. 有完整权限控制的多租户平台

## 10. 数据层现状

### 10.1 当前数据目录不是空壳

`data/` 下存在大量真实历史文件，说明平台已经跑过真实任务，而不是只搭了结构。

### 10.2 当前数据层组成

#### `data/configs/`

- `environments.json`
- `tools.json`

#### `data/tasks/`

保存任务状态 JSON。

特征：

1. 每个任务一个文件。
2. 字段通常包含：
   - `taskId`
   - `toolId`
   - `toolName`
   - `status`
   - `params`
   - `createdAt`
   - `updatedAt`
   - `returnCode`
   - `stdout`
   - `stderr`
   - `command`
   - `logFile`
   - `artifacts`
3. 部分任务还包含：
   - `uploads`
   - `artifactSpecs`
   - `executionMode`

#### `data/logs/`

保存每次执行的日志文本。

日志格式通常包括：

1. `[START]`
2. `[END]`
3. `[TOOL]`
4. `[RETURN_CODE]`
5. `[PARAMS]`
6. `[COMMAND]`
7. `[STDOUT]`
8. `[STDERR]`

#### `data/uploads/`

用于存放上传的原始文件或解压目录。

#### `data/artifacts/`

用于存放执行结果产物。

#### `data/reports/`

当前可见一份上线前验收报告：

- [data/reports/上线前验收清单_2026-05-01.md](/data/7G_Tool_Platform/data/reports/上线前验收清单_2026-05-01.md)

### 10.3 数据层反映出的一个重要事实

历史任务文件中有两类明显不同的数据风格：

#### A. 旧风格 / Windows 路径风格

例如：

- 命令中出现 `D:\Python311\python.exe`
- 路径中出现 `D:\PycharmProjects\...`

#### B. 新风格 / Linux 路径风格

例如：

- `/data/7G_Tool_Platform/data/plugins/...`
- `/usr/bin/python3`
- `/data/7G_Tool_Platform/data/uploads/...`

这说明：

1. 项目历史上至少跨两个运行环境被使用过。
2. 运行数据不是同一次单一部署生成的。
3. 仓库当前状态混合了不同阶段、不同机器、不同能力版本的执行痕迹。

## 11. 历史运行证据反映出的实际能力

### 11.1 验收报告反映的能力

[data/reports/上线前验收清单_2026-05-01.md](/data/7G_Tool_Platform/data/reports/上线前验收清单_2026-05-01.md) 明确记录：

1. 平台前端点击运行曾完成过一轮验收。
2. 当时至少 9 个工具通过。
3. 验收标准包括：
   - 可打开运行弹窗
   - 可提交执行
   - 状态为成功
   - 有日志文件
   - 退出码为 0

这说明“前端提交 -> 后端执行 -> 任务完成 -> 日志保存”这条主链路曾经是打通的。

### 11.2 历史任务文件反映出的增强能力

当前 `plugin_runner.py` 只处理：

1. 参数必填校验
2. 命令执行
3. 标准输出提取产物

但部分历史任务文件还体现出额外能力：

1. `uploads`
   - 记录上传文件的源文件名、保存路径、解析路径、上传类型
2. `artifactSpecs`
   - 记录输出目录、产物类型等
3. `executionMode`
   - 记录执行模式

例如：

- [data/tasks/6cb2da36dca244dbb0b3499b36ef78df.json](/data/7G_Tool_Platform/data/tasks/6cb2da36dca244dbb0b3499b36ef78df.json)
- [data/tasks/0ed5a71f96bf4baf8d8600c102c3c1e8.json](/data/7G_Tool_Platform/data/tasks/0ed5a71f96bf4baf8d8600c102c3c1e8.json)

这说明：

1. 仓库中的历史数据很可能来自一个更强版本的运行器。
2. 或者来自另一套同名平台代码。
3. 当前仓库代码并不能完整解释所有历史任务字段来源。

## 12. 当前代码与历史数据的断层

这是当前项目最关键的问题。

### 12.1 断层一：代码描述“少量工具”，历史数据反映“多插件平台”

当前：

- `tools.json` 只写了 2 个工具
- `backend/tools/` 只保留 2 个内置脚本副本

历史数据：

- 显示至少 20+ 个插件被执行过

### 12.2 断层二：当前代码没有通用上传逻辑，历史任务里有上传元信息

当前：

- 前端运行表单只渲染文本/选择控件
- 没有真正的文件上传组件
- 后端 `run` 接口只接收 JSON 参数

历史任务：

- 存在 `uploads`
- 存在 ZIP 解压路径
- 存在文件型和目录型上传记录

### 12.3 断层三：当前后端文档仍停留在“骨架阶段”

当前代码：

- 后端已经具备可运行能力

文档：

- 仍写“建议选择 FastAPI”

### 12.4 断层四：环境配置前后端不一致

当前前端：

- 保存到浏览器本地存储

当前后端：

- 只提供只读 `GET /api/environments`

结果：

- 前端环境配置不会真正影响后端运行

### 12.5 断层五：当前插件目录权限异常

当前仓库：

- 可以看到 `data/plugins/` 目录名
- 但无法读取目录内容

结果：

1. 当前代码分析无法基于插件真实内容完成闭环。
2. 当前仓库在别的机器上未必能直接复现历史运行能力。

## 13. 当前项目已经具备的真实价值

尽管有断层，这个项目已经不是空架子，仍然有明显价值。

### 13.1 作为内部工具平台的价值

它已经具备：

1. 基本工具目录展示
2. 统一参数提交
3. 统一执行入口
4. 统一任务记录
5. 统一日志保存
6. 统一产物查看

这对于内部工具台来说，价值已经成立。

### 13.2 作为插件平台雏形的价值

当前 manifest 体系和插件导入能力已经说明：

1. 平台思路是正确的
2. 新工具接入已经不必全部写死到代码里
3. 已经具备“平台化”的基本骨架

### 13.3 作为历史经验沉淀的价值

`data/tasks`、`data/logs`、`data/reports` 证明：

1. 工具平台不是纸面需求
2. 它被真实使用过
3. 它覆盖过标注、转换、清洗、YOLO、报告等多种任务

## 14. 当前主要问题清单

按重要性排序，当前问题可分为以下几类。

### 14.1 P0：版本与事实不一致

1. 文档、代码、历史数据三者不一致。
2. 当前仓库不能完整解释历史任务能力。
3. 当前 `data/plugins` 权限异常影响可维护性。

### 14.2 P1：部署与环境硬编码

1. 前后端地址硬编码 `192.168.54.120`
2. 启动脚本不适合换机器
3. 前端 API_BASE 写死

### 14.3 P1：配置链路未闭环

1. 前端环境配置不落后端
2. 后端环境配置接口只读
3. 实际执行无法稳定依赖环境中心

### 14.4 P1：运行模型偏弱

1. 使用标准库 HTTPServer
2. 无鉴权
3. 无任务取消
4. 无任务列表分页
5. 无统一错误码

### 14.5 P2：插件生态未收口

1. 旧 `tools.json` 格式仍保留
2. 内置工具和 manifest 插件体系并存
3. 参数类型规范没有完全统一

## 15. 当前适合做什么，不适合做什么

### 15.1 适合

1. 作为内部局域网工具平台继续演进
2. 作为插件式脚本调度平台的代码基础
3. 作为已有工具资产的统一入口
4. 作为后续重构前的业务样本仓库

### 15.2 不适合

1. 直接当成标准生产 SaaS 发布
2. 面向外部用户开放
3. 在不清理插件权限问题的前提下做长期维护
4. 在不统一配置与部署方式的前提下做跨环境复制

## 16. 后续建议路线

### 16.1 第一阶段：把“现状”稳定下来

建议先做这几件事：

1. 修复 `data/plugins/` 权限问题
2. 导出一份完整插件清单
3. 明确哪些插件仍有效、哪些是历史遗留
4. 统一更新 README 与 backend 文档，删除“骨架”表述
5. 把 `HOST` / `API_BASE` 改成配置项或环境变量

### 16.2 第二阶段：统一代码与历史能力

1. 确认历史任务中的 `uploads`、`artifactSpecs` 是由哪一版代码产生
2. 决定是：
   - 把当前代码补齐到历史能力
   - 还是把历史数据视为旧版遗留，重新定义现行能力边界
3. 若保留文件上传能力：
   - 前端补文件选择/上传
   - 后端补上传处理
   - 任务模型显式定义 uploads/artifactSpecs

### 16.3 第三阶段：做工程化改造

1. 将后端迁移到 FastAPI 或同类框架
2. 加入配置管理
3. 加入鉴权
4. 加入任务列表与任务检索
5. 加入更清晰的插件管理后台

## 17. 当前项目的最终判断

如果只问一句“这个项目现在是什么状态”，最准确的表述是：

这是一个已经跑通过真实任务的内部脚本工具平台，核心执行链路已具备，但仓库当前代码、文档说明、历史运行数据之间存在明显版本断层，短期内应先做“现状对齐”和“权限/配置收口”，再决定是继续迭代现有实现，还是基于现有业务事实做一轮体系化重构。

## 18. 附：关键文件索引

### 核心入口

- [start_platform.py](/data/7G_Tool_Platform/start_platform.py)

### 后端核心

- [backend/main.py](/data/7G_Tool_Platform/backend/main.py)
- [backend/storage.py](/data/7G_Tool_Platform/backend/storage.py)
- [backend/plugin_loader.py](/data/7G_Tool_Platform/backend/plugin_loader.py)
- [backend/plugin_installer.py](/data/7G_Tool_Platform/backend/plugin_installer.py)
- [backend/plugin_runner.py](/data/7G_Tool_Platform/backend/plugin_runner.py)
- [backend/manifest_schema.py](/data/7G_Tool_Platform/backend/manifest_schema.py)

### 内置工具

- [backend/tools/labelu_json_to_voc_xml.py](/data/7G_Tool_Platform/backend/tools/labelu_json_to_voc_xml.py)
- [backend/tools/labelu_task_create.py](/data/7G_Tool_Platform/backend/tools/labelu_task_create.py)

### 前端核心

- [frontend/index.html](/data/7G_Tool_Platform/frontend/index.html)
- [frontend/app.js](/data/7G_Tool_Platform/frontend/app.js)
- [frontend/styles.css](/data/7G_Tool_Platform/frontend/styles.css)

### 配置与运行数据

- [data/configs/tools.json](/data/7G_Tool_Platform/data/configs/tools.json)
- [data/configs/environments.json](/data/7G_Tool_Platform/data/configs/environments.json)
- [data/README.md](/data/7G_Tool_Platform/data/README.md)
- [data/reports/上线前验收清单_2026-05-01.md](/data/7G_Tool_Platform/data/reports/上线前验收清单_2026-05-01.md)

### 规范文档

- [README.md](/data/7G_Tool_Platform/README.md)
- [docs/PLUGIN_AUTHORING.md](/data/7G_Tool_Platform/docs/PLUGIN_AUTHORING.md)
