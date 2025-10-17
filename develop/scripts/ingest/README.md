# IELTS HTML Ingest Toolkit

本目录用于开发基于《脚本开发项目配置.md》的HTML→JSON转换脚本。脚本尚未实现，这里先完成运行环境骨架、配置解析模块和配置覆写机制。

## 虚拟环境初始化

推荐使用Python虚拟环境隔离依赖（参考文档第14.2节“依赖说明文件”要求）。

```bash
cd develop/scripts/ingest
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

以上命令基于`pyproject.toml`定义的最小工程化配置创建可编辑安装，后续可在`dependencies`字段中补充脚本所需第三方库。

## 配置文件

默认配置位于`settings.default.json`，覆盖典型开发环境：

- `paths.input_root` 指向仓库内原始HTML目录。
- `paths.output_root`、`paths.json_subdir`、`paths.chunks_subdir`与`paths.manifest_filename`描述文档规定的输出目录结构。
- `concurrency.max_workers` 定义脚本的最大并发度。

如需覆盖默认行为，在同一目录放置 `settings.local.json`，仅写入需要变更的字段即可（会与默认配置做深度合并）。示例：

```json
{
  "paths": {
    "output_root": "./tmp-output"
  },
  "concurrency": {
    "max_workers": 8
  }
}
```

> ⚠️ 请勿将包含真实路径或敏感信息的 `settings.local.json` 提交到版本库。示例文件仅用于说明字段格式。

## 配置加载器

`config_loader.py` 提供 `load_config()` 用于读取并验证配置：

- 默认从当前目录的 `settings.default.json` 加载基础配置。
- 如果存在 `settings.local.json`，会在保持嵌套结构的前提下覆盖默认值。
- 所有路径支持相对值（相对于配置文件所在目录）或绝对路径。
- 自动展开输出目录下的 `json`、`chunks` 子目录与 `manifest.json` 文件路径。
- 校验并发度必须为正整数。

示例：

```python
from pathlib import Path
from config_loader import load_config

config = load_config()
print(config.input_root)
print(config.output.json_dir)
print(config.concurrency)
```

返回值为数据类 `IngestConfig`，包含 `input_root`、`output`（含 `json_dir`、`chunks_dir`、`manifest_path`）与 `concurrency`。

后续脚本可在此基础上实现HTML解析、分块写入与manifest生成逻辑。
