# Jirin

**AI Agent for Android Stability Issue Analysis**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Version](https://img.shields.io/badge/version-0.5.0-orange.svg)

Jirin 是一个专注于 Android 稳定性问题分析的 AI Agent 工具。它能自动识别日志类型（JE / ANR / NE / MIXED），调用专业分析 Agent 进行深度根因分析，并输出结构化的分析报告。

---

## ✨ 功能特性

- 🔍 **多类型分析** — 支持 Java Exception、ANR、Native Crash 及 MIXED 混合问题深度分析
- 🧠 **自学习系统** — 从历史案例中学习，积累案例库，持续提升分析准确性
- 🔗 **多模型支持** — OpenAI / DeepSeek / 通义千问 / Kimi / Ollama 等多种 LLM 后端
- 📱 **多平台日志** — 自动识别高通 / MTK / 展锐日志目录结构
- 🔌 **IDE 插件导出** — 导出为 Qoder Skill / Cursor Rules / Codex AGENTS.md
- 📝 **灵活输出** — 支持纯文本 / Markdown / HTML 多种报告格式
- 🔄 **用户反馈闭环** — 分析后收集反馈，持续改进分析质量
- 📚 **AOSP 源码引用** — 内置 30+ 框架组件路径映射，自动引用关键源码路径

---

## 🚀 两种使用方式

### 方式 A：CLI 命令行工具

完整的 Agent 运行时，支持 LLM 调用、多 Agent 协作、自动学习。

```bash
pip install -e .
jirin analyze crash.log
```

### 方式 B：IDE 知识插件

将专业知识导出为规则文件，在 Cursor / Codex / Qoder 等 AI IDE 中使用。无需安装 Python 环境。

```bash
jirin export cursor --output ./.cursor/rules
```

| 对比项 | CLI 模式 | 插件模式 |
|--------|----------|----------|
| 运行环境 | 本机 Python | AI IDE |
| AI 模型 | 用户配置的 LLM | IDE 自带模型 |
| 需要 API Key | 是（Ollama 除外） | 否 |
| 自动学习 | 是 | 否 |

---

## 📦 安装（CLI 模式）

### 环境要求

- Python 3.11+

### 安装步骤

```bash
# 克隆项目
git clone https://github.com/PengFan001/Jirin.git
cd Jirin

# 安装（国内用户建议加镜像）
# pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
pip install -e .
```

### 配置 LLM

```bash
# 复制配置模板
cp config/settings.example.toml config/settings.toml
```

编辑 `config/settings.toml`，填入你的 API Key：

```toml
[llm]
provider = "openai"
model = "kimi-k2.7-code"
api_key = "sk-xxx"
api_base = "https://api.moonshot.cn/v1"
```

<details>
<summary>各模型配置示例</summary>

**DeepSeek**

```toml
[llm]
provider = "openai"
model = "deepseek-chat"
api_key = "sk-xxx"
api_base = "https://api.deepseek.com/v1"
```

**通义千问 (Qwen)**

```toml
[llm]
provider = "openai"
model = "qwen-plus"
api_key = "sk-xxx"
api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
```

**Ollama 本地模型（免费，无需 API Key）**

```toml
[llm]
provider = "ollama"
model = "qwen2.5:14b"
api_base = "http://localhost:11434"
```

</details>

### 验证配置

```bash
jirin test connection
```

### 功能可用性说明

> **安装后必须配置 LLM 才能使用分析功能。**

| 功能 | 是否需要 LLM | 说明 |
|------|-------------|------|
| `jirin version` | 否 | 查看版本信息，安装即可用 |
| `jirin config init` | 否 | 初始化配置文件，安装即可用 |
| `jirin export` | 否 | 导出知识文件到 IDE，安装即可用 |
| `jirin analyze` | **是** | 需要 LLM 进行智能分析 |
| `jirin learn` | 部分 | 案例管理无需 LLM；反思学习需要 |

> 💡 **零成本方案**：使用本地 Ollama 模型（如 `qwen2.5:14b`）无需任何 API Key，完全免费。

---

## 📖 使用方法

### 分析日志

```bash
# 分析单个日志文件
jirin analyze crash.log

# 分析日志目录（自动识别平台结构）
jirin analyze /path/to/logs/

# 详细模式 + 导出 Markdown 报告
jirin analyze crash.log --verbose --output report.md

# 指定配置文件
jirin analyze crash.log --config /path/to/settings.toml

# 跳过分析后的反馈提示（批量场景）
jirin analyze crash.log --no-feedback
```

**analyze 参数一览**

| 参数 | 说明 | 是否必须 |
|------|------|----------|
| `<log_path>` | 日志文件路径或日志目录路径 | 必须 |
| `--config, -c` | 配置文件路径（可选，自动发现） | 可选 |
| `--verbose, -v` | 显示详细分析过程 | 可选 |
| `--export, -e` | 导出格式：none（默认）/ md / html | 可选 |
| `--output, -o` | 保存报告到文件（自动识别格式） | 可选 |
| `--interactive/--no-feedback` | 启用/禁用分析后反馈提示（默认启用） | 可选 |

### 知识库管理

```bash
# 学习日志目录结构
jirin learn-structure my_custom_logs /path/to/logs/

# 查看知识库统计
jirin learn stats

# 列出历史案例
jirin learn list --type anr

# 添加纠正反馈
jirin learn feedback <case_id> --correction "正确的根因是..."
```

### 导出到 IDE

```bash
# 导出为 Cursor Rules
jirin export cursor --output ./.cursor/rules

# 导出为 Codex AGENTS.md
jirin export codex --output ./codex_config

# 导出为 Qoder Skill
jirin export qoder --output ./my_skill

# 导出为通用 Markdown 文档包
jirin export generic --output ./docs
```

**导出格式对照**

| 目标 IDE | 导出文件 | 放置位置 | 使用的 AI 模型 | 是否自动生效 |
|----------|----------|----------|---------------|-------------|
| Cursor | jirin.md + knowledge/ | .cursor/rules/ | Cursor 配置的模型 | 是 |
| Codex | AGENTS.md + jirin_knowledge/ | 项目根目录 | Codex 配置的模型 | 是 |
| Qoder | SKILL.md + assets/ | .qoder/skills/ | Qoder 配置的模型 | 需 /jirin 触发 |
| 通用 | Markdown 文档包 | 手动提供给 AI | 任意 AI 模型 | 需手动粘贴 |

> 导出后用户使用的是 IDE 自己的 AI 模型。Jirin 提供的是**专业知识和分析方法论**，AI 模型读取这些知识后就能进行专业级分析。只要文件放在正确位置，不需要额外配置。

### 其他命令

```bash
jirin version              # 查看版本
jirin test connection      # 测试 LLM 连接
jirin test models          # 查看可用模型列表
jirin config show          # 查看当前配置
jirin config set llm.model "deepseek-chat"  # 修改配置
jirin upgrade check        # 检查更新
jirin upgrade run          # 执行升级
```

---

## 🔄 分析流程

```
输入日志 → Orchestrator（分类+路由）→ 专业 Agent（JE/ANR/NE）→ Correlator（MIXED 关联）→ Summary（汇总报告）→ 反馈收集
```

当检测到多种问题类型（如 JE + ANR）时，系统会自动进行跨类型因果关联分析，确定因果链和修复优先级。

---

## 📱 支持的平台

| 平台 | 识别标志 | 主要日志文件 |
|------|----------|-------------|
| Qualcomm | logcat_all.txt, tombstones/, QPST/ | logcat_all.txt, tombstones/, kmsg.txt |
| MTK | mdlog/, MobileLog/, APLog/ | MobileLog/logcat.log, mdlog/*.log |
| SPRD | sprdlog/, modem_log/ | logcat.txt, modem_log/*.log |

---

## 🛠️ 技术栈

- **Agent 编排**: [LangGraph](https://github.com/langchain-ai/langgraph)
- **向量存储**: [ChromaDB](https://github.com/chroma-core/chroma)
- **HTTP 客户端**: [httpx](https://github.com/encode/httpx)
- **CLI 框架**: [Typer](https://github.com/tiangolo/typer) + [Rich](https://github.com/Textualize/rich)
- **构建工具**: [Hatchling](https://github.com/pypa/hatch)
- **数据验证**: [Pydantic](https://github.com/pydantic/pydantic)

---

## 📂 项目结构

```
Jirin/
├── src/jirin/
│   ├── agents/          # 分析 Agent（JE/ANR/NE/Summary）
│   ├── cli/             # 命令行接口
│   ├── core/            # 核心引擎（Orchestrator/LLM Client/State）
│   ├── export/          # 导出模块（Cursor/Codex/Qoder/Generic）
│   ├── knowledge/       # 知识库管理
│   ├── learning/        # 自学习系统
│   ├── tools/           # 工具集（日志解析器/代码搜索/设备管理）
│   └── utils/           # 工具函数
├── config/              # 配置文件
├── tests/               # 测试用例
└── docs/                # 文档
```

---

## 🖥️ 跨机器部署

### 方式一：复制整个项目目录

```bash
# 打包为 zip 复制到目标机器
cd /path/to/Jirin
# Windows: 压缩 Jirin 文件夹
# Linux/Mac: tar -czf jirin.tar.gz Jirin/
```

在目标机器上：

```bash
cd Jirin
pip install -e .
cp config/settings.example.toml config/settings.toml
# 编辑 settings.toml，填入 API Key
```

### 方式二：通过 Git 获取代码

```bash
git clone <repository-url> Jirin
cd Jirin
pip install -e .
cp config/settings.example.toml config/settings.toml
```

> **注意**：每台机器都需要独立执行 `pip install -e .` 安装步骤，并各自配置 `config/settings.toml`（包含 API Key）。`.jirin/` 目录中的学习数据（案例库、记忆）可以一并复制，也可以在新机器上从零开始积累。

---

## ⚠️ 注意事项

- **CLI 模式需要 LLM 配置**：首次使用 CLI 前必须配置 LLM API Key。如果使用本地模型（Ollama），请确保 Ollama 服务已启动。插件模式无需配置。
- **配置自动发现**：Jirin 会自动搜索当前工作目录和安装目录下的 `config/settings.toml`。所有命令的 `--config` 参数均为可选。
- **日志输入支持文件和目录**：`jirin analyze` 的参数既可以是单个日志文件路径，也可以是日志目录路径。目录模式下会自动识别高通/MTK/展锐平台结构。
- **飞书集成**：使用 `--export md` 或 `--output report.md` 生成的报告可直接导入飞书文档。
- **隐私安全**：使用云端 LLM 时请注意数据安全；如有顾虑，CLI 模式可使用本地模型（Ollama）。
- **AOSP 源码搜索**：系统内置 30+ Android 框架组件路径映射。如需深度搜索，可在 `config/settings.toml` 中配置 `[source] aosp_source_dir` 指向本地 AOSP 源码目录。

---

## ❓ 常见问题

<details>
<summary>CLI 分析结果不准确怎么办？</summary>
提供更完整的日志文件；使用 <code>jirin learn feedback</code> 添加反馈帮助系统学习。
</details>

<details>
<summary>LLM 调用失败？</summary>
检查 API Key 是否正确配置；运行 <code>jirin test connection</code> 验证连接；检查网络是否正常。
</details>

<details>
<summary>Ollama 连接失败？</summary>
确认 Ollama 服务已启动（默认端口 11434）：运行 <code>ollama list</code> 检查。
</details>

<details>
<summary>导出到 IDE 后如何使用？</summary>
将导出文件放入对应目录（如 <code>.cursor/rules/</code>），在 IDE Chat 中直接贴入日志即可，IDE 会自动加载知识规则。
</details>

<details>
<summary>如何卸载？</summary>

```bash
pip uninstall jirin -y
```

</details>

---

## 📄 License

MIT License

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

<p align="center">
  <strong>Jirin</strong> — Android Stability Analysis AI Agent<br>
  <sub>JE · ANR · NE · MIXED · 自学习 · 多平台 · 多模型</sub>
</p>
