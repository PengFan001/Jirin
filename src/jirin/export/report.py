"""Report generation module.

Supports multiple output formats:
- text: Plain text output to terminal (default)
- md: Markdown report (compatible with Feishu/Lark)
- html: HTML report with styling
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from jirin.core.state import AnalysisState

logger = logging.getLogger(__name__)


def format_text_output(state: AnalysisState) -> str:
    """Format analysis result as plain text.

    Args:
        state: Completed analysis state.

    Returns:
        Plain text string.
    """
    lines = []
    lines.append("=" * 60)
    lines.append("Jirin 分析报告")
    lines.append("=" * 60)
    lines.append("")

    # Summary
    types = ", ".join(t.value.upper() for t in state.detected_types)
    lines.append(f"问题类型: {types}")
    lines.append(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if state.log_source:
        lines.append(f"日志来源: {state.log_source}")
    lines.append("")

    # Agent results
    for agent_name, result in state.agent_results.items():
        lines.append("-" * 40)
        lines.append(f"[{agent_name}]")
        lines.append(f"  根因: {result.root_cause}")
        lines.append(f"  责任方: {result.responsible_party}")
        lines.append(f"  置信度: {result.confidence:.0%}")
        lines.append("")

        if result.key_evidence:
            lines.append("  关键证据:")
            for evidence in result.key_evidence:
                lines.append(f"    - {evidence}")
            lines.append("")

        if result.suggestions:
            lines.append("  修复建议:")
            for i, suggestion in enumerate(result.suggestions, 1):
                lines.append(f"    {i}. {suggestion}")
            lines.append("")

        if result.analysis_detail:
            lines.append("  详细分析:")
            lines.append(f"    {result.analysis_detail[:500]}")
            lines.append("")

    # Final report
    if state.final_report:
        lines.append("=" * 60)
        lines.append("综合报告")
        lines.append("=" * 60)
        lines.append(state.final_report)

    return "\n".join(lines)


def format_markdown(state: AnalysisState) -> str:
    """Format analysis result as Markdown (Feishu/Lark compatible).

    Args:
        state: Completed analysis state.

    Returns:
        Markdown string.
    """
    lines = []
    lines.append("# Jirin 分析报告")
    lines.append("")
    lines.append(f"**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    types = " / ".join(t.value.upper() for t in state.detected_types)
    lines.append(f"**问题类型**: {types}")
    if state.log_source:
        lines.append(f"**日志来源**: `{state.log_source}`")
    lines.append("")

    # Summary table
    lines.append("## 分析摘要")
    lines.append("")
    lines.append("| 分析项 | 结果 |")
    lines.append("|--------|------|")

    for agent_name, result in state.agent_results.items():
        lines.append(f"| **{agent_name}** 根因 | {result.root_cause} |")
        lines.append(f"| **{agent_name}** 责任方 | {result.responsible_party} |")
        lines.append(f"| **{agent_name}** 置信度 | {result.confidence:.0%} |")

    lines.append("")

    # Detailed analysis
    for agent_name, result in state.agent_results.items():
        lines.append(f"## {agent_name} 详细分析")
        lines.append("")

        if result.root_cause:
            lines.append(f"**根因**: {result.root_cause}")
            lines.append("")

        if result.key_evidence:
            lines.append("### 关键证据")
            lines.append("")
            for evidence in result.key_evidence:
                lines.append(f"- `{evidence}`")
            lines.append("")

        if result.suggestions:
            lines.append("### 修复建议")
            lines.append("")
            for i, suggestion in enumerate(result.suggestions, 1):
                lines.append(f"{i}. {suggestion}")
            lines.append("")

        if result.analysis_detail:
            lines.append("### 分析详情")
            lines.append("")
            lines.append(result.analysis_detail)
            lines.append("")

    # Final report
    if state.final_report:
        lines.append("---")
        lines.append("")
        lines.append("## 综合结论")
        lines.append("")
        lines.append(state.final_report)

    return "\n".join(lines)


def format_html(state: AnalysisState) -> str:
    """Format analysis result as styled HTML.

    Args:
        state: Completed analysis state.

    Returns:
        HTML string.
    """
    types = " / ".join(t.value.upper() for t in state.detected_types)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build agent sections
    agent_sections = []
    for agent_name, result in state.agent_results.items():
        evidence_html = ""
        if result.key_evidence:
            items = "\n".join(f"<li><code>{e}</code></li>" for e in result.key_evidence)
            evidence_html = f"<h4>关键证据</h4><ul>{items}</ul>"

        suggestions_html = ""
        if result.suggestions:
            items = "\n".join(f"<li>{s}</li>" for s in result.suggestions)
            suggestions_html = f"<h4>修复建议</h4><ol>{items}</ol>"

        detail_html = ""
        if result.analysis_detail:
            detail_html = f"<h4>分析详情</h4><pre>{result.analysis_detail}</pre>"

        agent_sections.append(f"""
        <div class="agent-card">
            <h3>{agent_name}</h3>
            <div class="result-meta">
                <span class="badge root-cause">根因: {_html_escape(result.root_cause)}</span>
                <span class="badge responsible">责任方: {_html_escape(result.responsible_party)}</span>
                <span class="badge confidence">置信度: {result.confidence:.0%}</span>
            </div>
            {evidence_html}
            {suggestions_html}
            {detail_html}
        </div>""")

    agents_html = "\n".join(agent_sections)
    final_html = f"<pre>{_html_escape(state.final_report)}</pre>" if state.final_report else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jirin 分析报告</title>
    <style>
        :root {{ --primary: #2563eb; --text: #1e293b; --bg: #f8fafc; --card: #fff; --border: #e2e8f0; }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); line-height: 1.7; padding: 24px; max-width: 960px; margin: 0 auto; }}
        h1 {{ color: var(--primary); margin-bottom: 16px; }}
        h2 {{ color: var(--primary); margin: 24px 0 12px; padding-bottom: 8px; border-bottom: 2px solid var(--primary); }}
        h3 {{ margin: 16px 0 8px; }}
        .meta {{ color: #64748b; margin-bottom: 24px; }}
        .agent-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 20px; margin: 16px 0; }}
        .result-meta {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }}
        .badge {{ padding: 4px 12px; border-radius: 16px; font-size: 0.85rem; }}
        .badge.root-cause {{ background: #fee2e2; color: #991b1b; }}
        .badge.responsible {{ background: #fef3c7; color: #92400e; }}
        .badge.confidence {{ background: #d1fae5; color: #065f46; }}
        pre {{ background: #1e293b; color: #e2e8f0; padding: 16px; border-radius: 8px; overflow-x: auto; font-size: 0.85rem; margin: 12px 0; }}
        code {{ font-family: monospace; background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; color: #be185d; }}
        pre code {{ background: none; padding: 0; color: inherit; }}
        ul, ol {{ margin: 8px 0 8px 24px; }}
        li {{ margin: 4px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
        th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
        th {{ background: #eff6ff; font-weight: 600; }}
    </style>
</head>
<body>
    <h1>Jirin 分析报告</h1>
    <div class="meta">
        <p>分析时间: {timestamp}</p>
        <p>问题类型: {types}</p>
        {"<p>日志来源: " + _html_escape(state.log_source) + "</p>" if state.log_source else ""}
    </div>

    <h2>分析摘要</h2>
    <table>
        <tr><th>分析项</th><th>结果</th></tr>
        {"".join(f'<tr><td><strong>{name}</strong> 根因</td><td>{_html_escape(r.root_cause)}</td></tr><tr><td><strong>{name}</strong> 责任方</td><td>{_html_escape(r.responsible_party)}</td></tr>' for name, r in state.agent_results.items())}
    </table>

    <h2>详细分析</h2>
    {agents_html}

    {f'<h2>综合结论</h2>{final_html}' if final_html else ""}
</body>
</html>"""


def save_report(
    state: AnalysisState,
    output_path: Path,
    format: str = "md",
) -> Path:
    """Save analysis report to file.

    Args:
        state: Completed analysis state.
        output_path: Output file path.
        format: Output format ("text", "md", "html").

    Returns:
        Path to the saved file.
    """
    if format == "md":
        content = format_markdown(state)
        if not output_path.suffix:
            output_path = output_path.with_suffix(".md")
    elif format == "html":
        content = format_html(state)
        if not output_path.suffix:
            output_path = output_path.with_suffix(".html")
    else:
        content = format_text_output(state)
        if not output_path.suffix:
            output_path = output_path.with_suffix(".txt")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    logger.info("Report saved to: %s", output_path)
    return output_path


def _html_escape(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
