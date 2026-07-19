---
kind: configuration_system
name: 基于 TOML 的运行时配置系统
category: configuration_system
scope:
    - '**'
source_files:
    - config/settings.example.toml
    - config/settings.toml
    - src/jirin/core/context.py
    - src/jirin/cli/commands/config.py
---

## 1. 使用的系统与工具
- 配置文件格式：TOML（`config/settings.toml`，模板 `config/settings.example.toml`）
- 解析库：Python ≥3.12 使用内置 `tomllib`，否则回退到第三方 `tomli`；写入使用 `tomli_w`
- CLI 管理：通过 Typer 子命令 `jirin config {show,init,set}` 提供查看、初始化与键值设置能力
- 运行时加载：由 `ExecutionContext` 在应用启动时读取并缓存为字典，再按命名空间暴露便捷访问器

## 2. 核心文件与位置
- 配置模板与默认配置：`config/settings.example.toml`、`config/settings.toml`
- 运行时加载与访问：`src/jirin/core/context.py`（`ExecutionContext`）
- CLI 配置管理命令：`src/jirin/cli/commands/config.py`
- 其他 CLI 命令对配置的引用（如 `export.py`、`learn.py`、`main.py`）均指向 `config/settings.toml`

## 3. 架构与约定
- **单文件集中式配置**：所有运行时参数集中在一个 TOML 文件中，按功能域分节：
  - `[llm]` / `[llm.ollama]`：LLM 提供商、模型、密钥、端点等
  - `[embedding]` / `[embedding.openai]`：向量嵌入模型与后端
  - `[knowledge]`：静态知识目录、相似案例检索阈值等
  - `[storage]`：本地数据、案例、内存、向量数据库路径
  - `[export]`：导出输出目录
- **版本兼容加载**：`context.py` 与 `config.py` 中统一采用 `sys.version_info >= (3, 12)` 分支选择 `tomllib`/`tomli`，保证 Python 3.8+ 可用。
- **上下文注入模式**：`ExecutionContext` 作为全局共享对象，持有已解析的配置字典并提供 `get_llm_config()`、`get_embedding_config()`、`get_knowledge_config()`、`get_storage_config()` 等强类型化访问方法；同时懒初始化 `KnowledgeManager`、`VectorStore`、`CaseStore`，将配置项按需注入。
- **CLI 驱动初始化**：`jirin config init` 从模板复制生成 `settings.toml`；`jirin config set <key> <value>` 支持 `a.b.c` 点号路径写入；`jirin config show` 以富文本打印当前配置。
- **默认值策略**：当配置缺失对应键时，`ExecutionContext` 的属性访问器提供合理默认值（如 `data/vector_db`、`src/jirin/knowledge/static`），避免硬编码散落各处。

## 4. 开发者应遵循的规则
- **新增配置项**：先在 `config/settings.example.toml` 中添加示例与注释，再同步到 `config/settings.toml`；在 `ExecutionContext` 中补充对应的 `get_xxx_config()` 或属性访问器，并在需要处消费该 accessor，而非直接操作原始字典。
- **不要绕过 `ExecutionContext`**：业务代码应通过 `ctx.get_*_config()` 获取配置片段，禁止在各模块内自行 `tomllib.load` 重复读取同一文件。
- **敏感信息处理**：`api_key` 等字段仅存在于本地 TOML，当前未集成环境变量覆盖或密钥管理服务；如需引入，应在 `load_config` 阶段做合并，并保持向后兼容。
- **CLI 写入规范**：通过 `jirin config set` 修改配置，避免手动编辑导致 TOML 结构损坏；若需批量更新，可在该命令基础上扩展子命令。
- **路径约定**：相对路径均以仓库根为基准（如 `data`、`src/jirin/knowledge/static`），部署时应确保工作目录一致或在 `ExecutionContext` 层增加前缀拼接逻辑。