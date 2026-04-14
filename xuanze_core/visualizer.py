# 选择.Skill — 可视化模块
"""
Visualizer 负责文本时间线和图表（饼图、折线图、词云）的渲染。

支持筛选条件（时间范围、标签）仅渲染子集。
历史记录少于 2 条时显示"数据不足"提示，不渲染空图表。

Requirements: R13.1, R13.2, R13.3, R14.1, R14.2, R14.3, R14.4
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from matplotlib.figure import Figure

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from xuanze_core.history import HistoryManager
from xuanze_core.models import DecisionType, HistoryRecord

# 图表最少记录数阈值
MIN_RECORDS_FOR_CHART = 2

# 决策类型中文标签
DECISION_TYPE_LABELS: dict[DecisionType, str] = {
    DecisionType.LONG_TERM: "长期选择",
    DecisionType.SHORT_TERM: "短期选择",
}

console = Console()


class Visualizer:
    """可视化模块

    提供文本时间线渲染和图表生成功能。
    通过 HistoryManager 获取历史记录，支持筛选条件。

    Args:
        history_manager: 历史记录管理器实例
    """

    def __init__(self, history_manager: HistoryManager) -> None:
        self.history_manager = history_manager

    # ── 筛选辅助方法 ──────────────────────────────────────

    def _filter_records(
        self,
        records: list[HistoryRecord],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        tags: list[str] | None = None,
    ) -> list[HistoryRecord]:
        """按时间范围和标签筛选记录子集。

        Args:
            records: 原始记录列表
            start_time: 起始时间（含），None 表示不限
            end_time: 结束时间（含），None 表示不限
            tags: 标签过滤列表，匹配任一即保留

        Returns:
            筛选后的记录列表
        """
        filtered = list(records)

        if start_time is not None:
            filtered = [r for r in filtered if r.timestamp >= start_time]
        if end_time is not None:
            filtered = [r for r in filtered if r.timestamp <= end_time]
        if tags:
            query_tags_lower = {t.lower() for t in tags}
            result: list[HistoryRecord] = []
            for record in filtered:
                record_tags_lower = {t.lower() for t in record.tags}
                if record_tags_lower & query_tags_lower:
                    result.append(record)
                    continue
                summary_lower = record.report.question_summary.lower()
                if any(tag.lower() in summary_lower for tag in tags):
                    result.append(record)
            filtered = result

        return filtered

    # ── 文本模式：时间线 ──────────────────────────────────

    def render_timeline(
        self,
        records: list[HistoryRecord],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """使用 rich 库渲染文本时间线。

        显示每条记录的时间戳、问题摘要、分类类型和 Top 推荐选项。
        少于 2 条记录时显示"数据不足"提示。

        Args:
            records: 历史记录列表
            start_time: 起始时间筛选
            end_time: 结束时间筛选
            tags: 标签筛选
        """
        subset = self._filter_records(records, start_time, end_time, tags)

        if len(subset) < MIN_RECORDS_FOR_CHART:
            console.print(
                Panel(
                    "📊 数据不足 — 至少需要 2 条历史记录才能渲染时间线。",
                    title="提示",
                    style="yellow",
                )
            )
            return

        # 按时间戳升序排列
        subset.sort(key=lambda r: r.timestamp)

        table = Table(
            title="📅 决策历史时间线",
            show_lines=True,
            expand=True,
        )
        table.add_column("时间", style="cyan", width=20)
        table.add_column("问题摘要", style="white")
        table.add_column("类型", style="magenta", width=10)
        table.add_column("Top 推荐", style="green")

        for record in subset:
            ts = record.timestamp.strftime("%Y-%m-%d %H:%M")
            summary = record.report.question_summary
            dtype = DECISION_TYPE_LABELS.get(
                record.classification, record.classification.value
            )
            # 取第一个推荐选项
            top_option = (
                record.report.recommended_options[0].name
                if record.report.recommended_options
                else "—"
            )
            table.add_row(ts, summary, dtype, top_option)

        console.print(table)

    # ── 图表模式：饼图 ────────────────────────────────────

    def render_pie_chart(
        self,
        records: list[HistoryRecord],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        tags: list[str] | None = None,
    ) -> Figure | None:
        """生成决策类型分布饼图。

        使用 matplotlib 绘制长期选择 vs 短期选择的占比。
        少于 2 条记录时显示提示并返回 None。

        Args:
            records: 历史记录列表
            start_time: 起始时间筛选
            end_time: 结束时间筛选
            tags: 标签筛选

        Returns:
            matplotlib Figure 对象，数据不足时返回 None
        """
        import matplotlib.pyplot as plt

        subset = self._filter_records(records, start_time, end_time, tags)

        if len(subset) < MIN_RECORDS_FOR_CHART:
            console.print(
                Panel(
                    "📊 数据不足 — 至少需要 2 条历史记录才能生成饼图。",
                    title="提示",
                    style="yellow",
                )
            )
            return None

        # 统计各类型数量
        counter: Counter[str] = Counter()
        for record in subset:
            label = DECISION_TYPE_LABELS.get(
                record.classification, record.classification.value
            )
            counter[label] += 1

        labels = list(counter.keys())
        sizes = list(counter.values())
        colors = ["#4FC3F7", "#FFB74D"]  # 蓝色=长期, 橙色=短期

        fig, ax = plt.subplots(figsize=(6, 6))
        ax.pie(
            sizes,
            labels=labels,
            autopct="%1.1f%%",
            colors=colors[: len(labels)],
            startangle=90,
        )
        ax.set_title("决策类型分布")
        fig.tight_layout()
        return fig

    # ── 图表模式：折线图 ──────────────────────────────────

    def render_line_chart(
        self,
        records: list[HistoryRecord],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        tags: list[str] | None = None,
    ) -> Figure | None:
        """生成每月决策数量折线图。

        X 轴为月份（YYYY-MM），Y 轴为该月决策数量。
        少于 2 条记录时显示提示并返回 None。

        Args:
            records: 历史记录列表
            start_time: 起始时间筛选
            end_time: 结束时间筛选
            tags: 标签筛选

        Returns:
            matplotlib Figure 对象，数据不足时返回 None
        """
        import matplotlib.pyplot as plt

        subset = self._filter_records(records, start_time, end_time, tags)

        if len(subset) < MIN_RECORDS_FOR_CHART:
            console.print(
                Panel(
                    "📊 数据不足 — 至少需要 2 条历史记录才能生成折线图。",
                    title="提示",
                    style="yellow",
                )
            )
            return None

        # 按月份统计
        monthly: Counter[str] = Counter()
        for record in subset:
            month_key = record.timestamp.strftime("%Y-%m")
            monthly[month_key] += 1

        # 按月份排序
        sorted_months = sorted(monthly.keys())
        counts = [monthly[m] for m in sorted_months]

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(sorted_months, counts, marker="o", color="#4FC3F7", linewidth=2)
        ax.set_xlabel("月份")
        ax.set_ylabel("决策数量")
        ax.set_title("每月决策数量趋势")
        ax.grid(True, alpha=0.3)

        # X 轴标签旋转以防重叠
        if len(sorted_months) > 6:
            plt.xticks(rotation=45, ha="right")

        fig.tight_layout()
        return fig

    # ── 图表模式：词云 ────────────────────────────────────

    def render_word_cloud(
        self,
        records: list[HistoryRecord],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        tags: list[str] | None = None,
    ) -> Figure | None:
        """生成关键词词云。

        从所有记录的问题摘要和标签中提取关键词，
        使用 wordcloud 库生成词云图。
        少于 2 条记录时显示提示并返回 None。

        Args:
            records: 历史记录列表
            start_time: 起始时间筛选
            end_time: 结束时间筛选
            tags: 标签筛选

        Returns:
            matplotlib Figure 对象，数据不足时返回 None
        """
        import matplotlib.pyplot as plt
        from wordcloud import WordCloud

        subset = self._filter_records(records, start_time, end_time, tags)

        if len(subset) < MIN_RECORDS_FOR_CHART:
            console.print(
                Panel(
                    "📊 数据不足 — 至少需要 2 条历史记录才能生成词云。",
                    title="提示",
                    style="yellow",
                )
            )
            return None

        # 收集所有关键词文本
        text_parts: list[str] = []
        for record in subset:
            text_parts.append(record.report.question_summary)
            text_parts.extend(record.tags)
            for option in record.report.recommended_options:
                text_parts.append(option.name)

        combined_text = " ".join(text_parts)

        if not combined_text.strip():
            console.print(
                Panel(
                    "📊 无有效关键词数据，无法生成词云。",
                    title="提示",
                    style="yellow",
                )
            )
            return None

        # 生成词云
        wc = WordCloud(
            width=800,
            height=400,
            background_color="white",
            max_words=100,
            colormap="viridis",
        )
        wc.generate(combined_text)

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        ax.set_title("决策关键词词云")
        fig.tight_layout()
        return fig
