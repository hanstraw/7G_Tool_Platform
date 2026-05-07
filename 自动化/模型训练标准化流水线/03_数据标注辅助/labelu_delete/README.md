# LabelU 删除脚本

这个脚本用于批量删除 LabelU 指定任务中指定状态的样本，默认场景是删除 `SKIPPED`, 即标注为跳过类型。

## 快速上手

使用python3.9+, 先安装依赖：

```bash
pip install requests pyyaml
```

然后修改 [config.yaml]里的这几个值：

- `base_url`：你的 LabelU 地址
- `token`：有删除权限的 token，不要带 `Bearer `
- `target.task_id`：要处理的任务 ID



用下面方法启动, 确认数量没问题后，再按'y'正式删除：
```bash
python delete_skip.py
```

## 常用命令

只扫描不删除：

```bash
python delete_skip.py --dry-run
```

跳过确认，直接删除：

```bash
python delete_skip.py --yes
```

临时指定任务 ID：

```bash
python delete_skip.py --task-id 200
```

临时指定多个状态：

```bash
python delete_skip.py --states SKIPPED NEW 
```

## 说明

- 配置文件里已经有逐行中文注释，直接按注释改即可
- 参数可以组合使用
- 删除失败时会生成 `failed_batches.json`
