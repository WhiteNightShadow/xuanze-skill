# 选择.Skill — 导出模块
"""
Exporter 负责将决策报告和历史记录导出为 Markdown / PDF / PNG 格式。

- Markdown：纯文本格式化输出
- PDF：使用 fpdf2 生成，支持中文字符
- PNG：将 matplotlib Figure 保存为图片

缺少依赖时显示描述性错误信息和安装命令。

Requirements: R15.1, R15.2, R15.3, R15.4
"""

from __future__ import annotations

import os
from typing import Union

from matplotlib.figure import Figure

from xuanze_core.models import (
    DecisionReport,
    DecisionType,
    ExportFormat,
    HistoryRecord,
    RecommendedOption,
)

# 决策类型中文标签
_DECISION_TYPE_LABELS: dict[DecisionType, str] = {
    DecisionType.LONG_TERM: "长期选择",
    DecisionType.SHORT_TERM: "短期选择",
}

# 支持的导出数据类型
ExportData = Union[DecisionReport, list[HistoryRecord]]


class Exporter:
    """导出模块

    提供统一的 export() 接口，根据格式分发到
    to_markdown / to_pdf / to_png 具体实现。
    """

    def __init__(self) -> None:
        pass

    # ── 统一导出接口 ──────────────────────────────────────

    def export(
        self,
        data: ExportData,
        format: ExportFormat,
        output_path: str,
    ) -> str:
        """统一导出接口，返回输出文件路径。

        Args:
            data: DecisionReport 或 list[HistoryRecord]
            format: 导出格式（markdown / pdf / png）
            output_path: 输出文件路径

        Returns:
            实际写入的文件路径

        Raises:
            ValueError: 数据类型与导出格式不匹配
            ImportError: 缺少必要依赖
        """
        # 确保输出目录存在
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        if format == ExportFormat.MARKDOWN:
            md_content = self.to_markdown(data)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            return output_path

        if format == ExportFormat.PDF:
            md_content = self.to_markdown(data)
            return self.to_pdf(md_content, output_path)

        if format == ExportFormat.PNG:
            if not isinstance(data, Figure):
                raise ValueError(
                    "PNG 导出需要传入 matplotlib Figure 对象。"
                    "请先通过 Visualizer 生成图表，再调用导出。"
                )
            return self.to_png(data, output_path)

        raise ValueError(f"不支持的导出格式: {format}")

    # ── Markdown 生成 ─────────────────────────────────────

    def to_markdown(self, data: ExportData) -> str:
        """将 DecisionReport 或 HistoryRecord 列表转为格式化 Markdown。

        Args:
            data: 决策报告或历史记录列表

        Returns:
            Markdown 格式字符串
        """
        if isinstance(data, DecisionReport):
            return self._report_to_markdown(data)

        if isinstance(data, list):
            return self._history_to_markdown(data)

        raise ValueError(
            f"不支持的数据类型: {type(data).__name__}，"
            "请传入 DecisionReport 或 list[HistoryRecord]。"
        )

    def _report_to_markdown(self, report: DecisionReport) -> str:
        """单份决策报告 → Markdown。"""
        lines: list[str] = []
        dtype_label = _DECISION_TYPE_LABELS.get(
            report.classification, report.classification.value
        )

        lines.append(f"# 决策报告：{report.question_summary}")
        lines.append("")
        lines.append(f"- **分类**: {dtype_label}")
        lines.append(f"- **时间**: {report.timestamp.strftime('%Y-%m-%d %H:%M')}")
        lines.append("")

        # 推荐选项
        if report.recommended_options:
            lines.append("## 推荐选项")
            lines.append("")
            for i, opt in enumerate(report.recommended_options, 1):
                lines.extend(self._option_to_markdown(opt, i))

        # 个性化建议
        if report.personalized_suggestions:
            lines.append("## 个性化建议")
            lines.append("")
            lines.append(report.personalized_suggestions)
            lines.append("")

        # 信息来源
        if report.source_references:
            lines.append("## 信息来源")
            lines.append("")
            for ref in report.source_references:
                lines.append(f"- {ref}")
            lines.append("")

        return "\n".join(lines)

    def _option_to_markdown(self, opt: RecommendedOption, index: int) -> list[str]:
        """单个推荐选项 → Markdown 片段。"""
        lines: list[str] = []
        score_str = f"（评分: {opt.score:.1f}）" if opt.score is not None else ""
        lines.append(f"### {index}. {opt.name}{score_str}")
        lines.append("")
        lines.append(f"**推荐理由**: {opt.reasoning}")
        lines.append("")

        if opt.pros:
            lines.append("**优势**:")
            for pro in opt.pros:
                lines.append(f"- ✅ {pro}")
            lines.append("")

        if opt.cons:
            lines.append("**劣势**:")
            for con in opt.cons:
                lines.append(f"- ⚠️ {con}")
            lines.append("")

        if opt.risk_warnings:
            lines.append("**风险提示**:")
            for risk in opt.risk_warnings:
                lines.append(f"- 🔴 {risk}")
            lines.append("")

        return lines

    def _history_to_markdown(self, records: list[HistoryRecord]) -> str:
        """历史记录列表 → Markdown。"""
        if not records:
            return "# 决策历史\n\n暂无历史记录。\n"

        lines: list[str] = []
        lines.append("# 决策历史")
        lines.append("")
        lines.append(f"共 {len(records)} 条记录")
        lines.append("")

        # 按时间倒序排列
        sorted_records = sorted(records, key=lambda r: r.timestamp, reverse=True)

        for record in sorted_records:
            dtype_label = _DECISION_TYPE_LABELS.get(
                record.classification, record.classification.value
            )
            ts = record.timestamp.strftime("%Y-%m-%d %H:%M")
            lines.append(f"## {ts} — {record.report.question_summary}")
            lines.append("")
            lines.append(f"- **类型**: {dtype_label}")

            if record.tags:
                lines.append(f"- **标签**: {', '.join(record.tags)}")

            # 简要列出推荐选项
            if record.report.recommended_options:
                lines.append("- **推荐选项**:")
                for opt in record.report.recommended_options:
                    lines.append(f"  - {opt.name}: {opt.reasoning}")

            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    # ── PDF 生成 ──────────────────────────────────────────

    def to_pdf(self, markdown_content: str, output_path: str) -> str:
        """将 Markdown 内容转为 PDF 文件，支持中文字符。

        使用 fpdf2 库生成 PDF。若未安装则抛出描述性错误。

        Args:
            markdown_content: Markdown 格式文本
            output_path: PDF 输出路径

        Returns:
            实际写入的文件路径

        Raises:
            ImportError: fpdf2 未安装
        """
        try:
            from fpdf import FPDF  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "PDF 导出需要 fpdf2 库。请运行以下命令安装：\n"
                "  pip install fpdf2"
            )

        # 确保输出目录存在
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # 尝试加载支持中文的字体
        font_loaded = self._load_cjk_font(pdf)
        if not font_loaded:
            # 回退到内置 Helvetica（中文字符可能显示为方块）
            pdf.set_font("Helvetica", size=10)

        # 逐行解析 Markdown 并写入 PDF
        for line in markdown_content.split("\n"):
            stripped = line.strip()

            if stripped.startswith("# ") and not stripped.startswith("## "):
                # 一级标题
                if font_loaded:
                    pdf.set_font("CJK", "B", 18)
                else:
                    pdf.set_font("Helvetica", "B", 18)
                pdf.cell(0, 12, stripped.lstrip("# "), new_x="LMARGIN", new_y="NEXT")
                pdf.ln(4)

            elif stripped.startswith("## ") and not stripped.startswith("### "):
                # 二级标题
                if font_loaded:
                    pdf.set_font("CJK", "B", 14)
                else:
                    pdf.set_font("Helvetica", "B", 14)
                pdf.cell(0, 10, stripped.lstrip("# "), new_x="LMARGIN", new_y="NEXT")
                pdf.ln(3)

            elif stripped.startswith("### "):
                # 三级标题
                if font_loaded:
                    pdf.set_font("CJK", "B", 12)
                else:
                    pdf.set_font("Helvetica", "B", 12)
                pdf.cell(0, 8, stripped.lstrip("# "), new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)

            elif stripped.startswith("---"):
                # 分隔线
                pdf.ln(3)
                y = pdf.get_y()
                pdf.line(10, y, 200, y)
                pdf.ln(3)

            elif stripped == "":
                # 空行
                pdf.ln(3)

            else:
                # 普通文本（去除 Markdown 加粗标记）
                if font_loaded:
                    pdf.set_font("CJK", size=10)
                else:
                    pdf.set_font("Helvetica", size=10)
                clean_text = stripped.replace("**", "")
                pdf.multi_cell(0, 6, clean_text)

        pdf.output(output_path)
        return output_path

    def _load_cjk_font(self, pdf: "FPDF") -> bool:  # noqa: F821
        """尝试加载支持中文的 CJK 字体。

        按优先级搜索 macOS / Linux / Windows 常见中文字体路径。

        Args:
            pdf: fpdf2 的 FPDF 实例

        Returns:
            是否成功加载中文字体
        """
        # 常见中文字体路径（按平台分组搜索）
        font_candidates = [
            # macOS
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            # Linux
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            # Windows
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simsun.ttc",
            "C:/Windows/Fonts/simhei.ttf",
        ]

        for font_path in font_candidates:
            if os.path.exists(font_path):
                try:
                    pdf.add_font("CJK", "", font_path, uni=True)  # type: ignore[attr-defined]
                    pdf.add_font("CJK", "B", font_path, uni=True)  # type: ignore[attr-defined]
                    pdf.set_font("CJK", size=10)  # type: ignore[attr-defined]
                    return True
                except Exception:
                    continue

        return False

    # ── PNG 生成 ──────────────────────────────────────────

    def to_png(self, figure: Figure, output_path: str) -> str:
        """将 matplotlib Figure 保存为 PNG 图片。

        Args:
            figure: matplotlib Figure 对象
            output_path: PNG 输出路径

        Returns:
            实际写入的文件路径

        Raises:
            ValueError: figure 不是有效的 matplotlib Figure
        """
        if not isinstance(figure, Figure):
            raise ValueError(
                "to_png() 需要传入 matplotlib.figure.Figure 对象。"
            )

        # 确保输出目录存在
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        figure.savefig(output_path, dpi=150, bbox_inches="tight")
        return output_path
