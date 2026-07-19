---
kind: error_handling
name: 错误处理：基于 try/except 的局部容错与 CLI 统一出口模式
category: error_handling
scope:
    - '**'
source_files:
    - src/jirin/cli/main.py
    - src/jirin/agents/base.py
    - src/jirin/core/orchestrator.py
    - src/jirin/agents/summary_agent.py
---

## 1. 采用的系统/方法
- **无自定义异常类型体系**：仓库未定义任何 `class *Error` 或专用异常类，也未使用 sentinel error、错误码枚举等结构化错误模型。
- **以 try/except 做局部容错**：在 LLM 调用、JSON 解析、知识检索等易失败处用 `try/except Exception` 捕获并降级为默认值或空结果，保证分析流程不中断。
- **CLI 层统一出口**：Typer 入口通过 `raise typer.Exit(1)` 退出，并用 Rich 面板打印错误信息；内部异常被顶层 `except Exception` 捕获后转为友好提示。
- **无全局日志框架**：未发现 `logging` / `loguru` 等配置，错误仅通过 `console.print` 输出到终端。
- **无 panic/recover 或中间件机制**：Python 生态下不存在 panic/recover；项目也未实现 HTTP 中间件式的全局错误拦截器。

## 2. 关键文件与位置
- `src/jirin/cli/main.py` — Typer 应用入口，集中处理参数校验失败、空日志、分析异常，并以 `typer.Exit(1)` 返回非零状态码。
- `src/jirin/agents/base.py` — BaseAgent._call_llm 中用 `try/except Exception` 包裹 litellm.completion，失败时返回 `[LLM Error: ...]` 字符串；_parse_response 对 JSON 解析失败回退为原始文本。
- `src/jirin/core/orchestrator.py` — _llm_classify、_retrieve_knowledge、_retrieve_similar_cases 均以 bare `except Exception` 吞掉异常并返回空列表，确保分类/检索失败不影响后续流程。
- `src/jirin/agents/summary_agent.py` — 同样用 `try/except Exception as e` 包裹可能失败的逻辑块。

## 3. 架构与约定
- **分层容错策略**：
  - 外部依赖（LLM、向量库）调用一律 try/except 并降级为“空/默认”，体现“尽可能完成分析”的鲁棒性设计。
  - 业务核心（Orchestrator 分类、Agent 分析）不被单个 I/O 失败打断。
- **错误传播边界**：只有 CLI 层将异常转换为用户可见消息和退出码；库函数本身不抛出领域异常，而是返回空结构体或降级结果。
- **结果对象携带警告**：`AnalysisState.final_report` 对应的结果对象包含 `errors` 字段，CLI 在最后统一打印“分析过程中出现的 N 个 issue”。

## 4. 开发者应遵循的规则
1. **不要抛出自定义异常**：当前代码库没有异常类型体系，新增功能应沿用 try/except 降级模式，而非 raise 新异常。
2. **外部调用必须兜底**：所有 LLM 调用、网络请求、I/O 操作都应包裹 try/except，失败时返回空字符串/空列表/默认对象，避免向上冒泡。
3. **CLI 是唯一的错误出口**：业务模块不应直接调用 `typer.Exit` 或 Rich 打印；只返回数据，由 CLI 层负责格式化与退出码。
4. **利用结果对象的 errors 字段**：若某步骤产生可恢复的告警，追加到 `state.errors` 列表，让最终报告汇总展示。
5. **避免 bare except 滥用**：虽然现有代码大量使用 `except Exception`，但在新写代码中应尽量捕获具体异常类型（如 `json.JSONDecodeError`、`litellm.exceptions.*`），以便未来接入结构化日志。
6. **暂不引入日志框架**：当前无 logging 配置，如需记录调试信息，优先使用 Rich 的 console 输出，保持与 CLI 风格一致。