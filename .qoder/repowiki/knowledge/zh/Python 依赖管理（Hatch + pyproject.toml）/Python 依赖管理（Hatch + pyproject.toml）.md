---
kind: dependency_management
name: Python 依赖管理（Hatch + pyproject.toml）
category: dependency_management
scope:
    - '**'
source_files:
    - pyproject.toml
---

本项目采用纯 `pyproject.toml` 声明式依赖管理，构建后端使用 Hatchling，未引入 pip-tools、Poetry、uv 等第三方依赖锁定工具。核心约定如下：

1. **单一声明源**：所有运行时与可选依赖集中在 `pyproject.toml` 的 `[project.dependencies]` 与 `[project.optional-dependencies]` 中，不存在 `requirements.txt`、`Pipfile`、`poetry.lock` 等并行清单。
2. **版本策略**：全部使用宽松下限约束（`>=X.Y.Z`），未做精确锁定；条件依赖通过 PEP 508 环境标记表达，如 `tomli>=2.0.0;python_version<'3.12'`。
3. **构建系统**：`[build-system]` 指定 `requires = ["hatchling"]`，`[tool.hatch.build.targets.wheel]` 将包目录映射为 `src/jirin`，发布产物为 wheel。
4. **可执行入口**：通过 `[project.scripts]` 注册 CLI 命令 `jirin -> jirin.cli.main:app`，由 Typer 驱动。
5. **开发依赖分组**：测试、lint、类型检查工具统一归入 `dev` 可选组，安装方式为 `pip install -e .[dev]`。
6. **无私有仓库/代理配置**：未发现 `.pypirc`、`pip.conf`、`PIP_INDEX_URL` 或 `PYPI_MIRROR` 等自定义索引配置，默认走 PyPI。
7. **无 vendoring / lockfile**：仓库内无 `vendor/`、`requirements.lock`、`poetry.lock`、`uv.lock` 等文件，也不存在任何 CI 脚本对依赖进行缓存或锁定。