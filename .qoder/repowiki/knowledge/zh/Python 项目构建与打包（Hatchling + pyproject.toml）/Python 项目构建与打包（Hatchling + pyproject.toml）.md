---
kind: build_system
name: Python 项目构建与打包（Hatchling + pyproject.toml）
category: build_system
scope:
    - '**'
source_files:
    - pyproject.toml
---

本项目采用纯 Python 现代构建体系，所有构建、打包、依赖声明与工具链配置均集中在根目录的 pyproject.toml 中，未引入 Makefile、Dockerfile、CI 流水线或外部脚本。

1. 构建系统：使用 Hatchling 作为后端（hatchling.build），通过 hatch build / hatch publish 完成 wheel 包生成与发布；包入口由 [project.scripts] 注册为 CLI 命令 jirin，指向 src/jirin/cli/main:app。

2. 依赖管理：核心运行依赖在 [project.dependencies] 中声明，开发依赖（pytest、ruff、mypy）放入 [project.optional-dependencies.dev]，通过 pip install .[dev] 安装。Python 版本要求 >=3.11，并针对 <3.12 条件引入 tomli。

3. 代码质量与测试：Ruff 用于 lint（目标版本 py311，启用 E/F/I/N/W 规则集），Mypy 开启 strict 模式，Pytest 自动发现 tests/ 下的异步测试。

4. 打包约定：Hatch 仅打包 src/jirin 目录为 wheel，符合 PEP 420 命名空间包布局。

5. 缺失环节：仓库中未发现 Docker 镜像构建、CI/CD 流水线、版本自动化（bumpversion/hatch-vcs）、交叉编译或发布到 PyPI 的自动化脚本——这些需后续补充。