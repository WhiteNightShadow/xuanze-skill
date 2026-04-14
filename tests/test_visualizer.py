# 选择.Skill — Visualizer 单元测试
"""
测试 Visualizer 的时间线渲染、饼图、折线图、词云生成，
以及数据不足提示和筛选条件逻辑。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from xuanze_core.history import HistoryManager
from xuanze_core.models import (
    DecisionReport,
    DecisionType,
    HistoryRecord,
    RecommendedOption,
)
from xuanze_core.visualizer import Visualizer


# ── 测试辅助 ──────────────────────────────────────────────


def _make_record(
    summary: str = "测试问题",
    dtype: DecisionType = DecisionType.SHORT_TERM,
    ts: datetime | None = None,
    tags: list[str] | None = None,
    option_name: str = "选项A",
) -> HistoryRecord:
    """快速构建一条 HistoryRecord。"""
    return HistoryRecord(
        report=DecisionReport(
            question_summary=summary,
            classification=dtype,
            recommended_options=[
                RecommendedOption(
                    name=option_name,
                    reasoning="理由",
                    pros=["优势"],
                    cons=["劣势"],
                )
            ],
            personalized_suggestions="建议",
        ),
        classification=dtype,
        timestamp=ts or datetime.now(),
        tags=tags or [],
    )


def _make_records(n: int, base_time: datetime | None = None) -> list[HistoryRecord]:
    """生成 n 条记录，时间间隔 1 天。"""
    base = base_time or datetime(2024, 1, 1)
    records = []
    for i in range(n):
        dtype = DecisionType.LONG_TERM if i % 2 == 0 else DecisionType.SHORT_TERM
        records.append(
            _make_record(
                summary=f"问题{i}",
                dtype=dtype,
                ts=base + timedelta(days=i),
                tags=[f"标签{i}"],
                option_name=f"选项{i}",
            )
        )
    return records


@pytest.fixture
def visualizer(tmp_path):
    """创建使用临时目录的 Visualizer 实例。"""
    hm = HistoryManager(cache_dir=str(tmp_path))
    return Visualizer(history_manager=hm)


# ── 数据不足提示测试 ──────────────────────────────────────


class TestInsufficientData:
    """历史记录少于 2 条时应显示数据不足提示。"""

    def test_timeline_empty(self, visualizer: Visualizer, capsys):
        """空记录列表应显示提示。"""
        visualizer.render_timeline([])
        # render_timeline 使用 rich console，不会被 capsys 捕获
        # 但不应抛出异常

    def test_timeline_one_record(self, visualizer: Visualizer):
        """单条记录应显示提示，不抛异常。"""
        records = [_make_record()]
        visualizer.render_timeline(records)

    def test_pie_chart_empty(self, visualizer: Visualizer):
        """空记录应返回 None。"""
        result = visualizer.render_pie_chart([])
        assert result is None

    def test_pie_chart_one_record(self, visualizer: Visualizer):
        """单条记录应返回 None。"""
        result = visualizer.render_pie_chart([_make_record()])
        assert result is None

    def test_line_chart_empty(self, visualizer: Visualizer):
        """空记录应返回 None。"""
        result = visualizer.render_line_chart([])
        assert result is None

    def test_line_chart_one_record(self, visualizer: Visualizer):
        """单条记录应返回 None。"""
        result = visualizer.render_line_chart([_make_record()])
        assert result is None

    def test_word_cloud_empty(self, visualizer: Visualizer):
        """空记录应返回 None。"""
        result = visualizer.render_word_cloud([])
        assert result is None

    def test_word_cloud_one_record(self, visualizer: Visualizer):
        """单条记录应返回 None。"""
        result = visualizer.render_word_cloud([_make_record()])
        assert result is None


# ── 正常渲染测试 ──────────────────────────────────────────


class TestNormalRendering:
    """有足够数据时应正常渲染。"""

    def test_timeline_renders(self, visualizer: Visualizer):
        """2 条以上记录应正常渲染时间线，不抛异常。"""
        records = _make_records(3)
        visualizer.render_timeline(records)

    def test_pie_chart_returns_figure(self, visualizer: Visualizer):
        """应返回 matplotlib Figure 对象。"""
        import matplotlib
        matplotlib.use("Agg")
        records = _make_records(4)
        fig = visualizer.render_pie_chart(records)
        assert fig is not None
        from matplotlib.figure import Figure
        assert isinstance(fig, Figure)

    def test_line_chart_returns_figure(self, visualizer: Visualizer):
        """应返回 matplotlib Figure 对象。"""
        import matplotlib
        matplotlib.use("Agg")
        records = _make_records(5)
        fig = visualizer.render_line_chart(records)
        assert fig is not None
        from matplotlib.figure import Figure
        assert isinstance(fig, Figure)

    def test_word_cloud_returns_figure(self, visualizer: Visualizer):
        """应返回 matplotlib Figure 对象。"""
        import matplotlib
        matplotlib.use("Agg")
        records = _make_records(3)
        fig = visualizer.render_word_cloud(records)
        assert fig is not None
        from matplotlib.figure import Figure
        assert isinstance(fig, Figure)


# ── 筛选条件测试 ──────────────────────────────────────────


class TestFiltering:
    """筛选条件应正确过滤记录。"""

    def test_time_range_filter(self, visualizer: Visualizer):
        """时间范围筛选应只保留范围内的记录。"""
        import matplotlib
        matplotlib.use("Agg")
        base = datetime(2024, 1, 1)
        records = _make_records(10, base_time=base)

        # 只取前 3 天的记录 → 不足 2 条不会发生，3 条
        fig = visualizer.render_pie_chart(
            records,
            start_time=base,
            end_time=base + timedelta(days=2),
        )
        assert fig is not None

    def test_time_range_filter_too_narrow(self, visualizer: Visualizer):
        """时间范围过窄导致不足 2 条时应返回 None。"""
        base = datetime(2024, 1, 1)
        records = _make_records(10, base_time=base)

        # 只取第 1 天 → 1 条
        fig = visualizer.render_pie_chart(
            records,
            start_time=base,
            end_time=base,
        )
        assert fig is None

    def test_tag_filter(self, visualizer: Visualizer):
        """标签筛选应只保留匹配的记录。"""
        import matplotlib
        matplotlib.use("Agg")
        records = _make_records(5)

        # 筛选 "标签0" 和 "标签1" → 2 条
        fig = visualizer.render_pie_chart(records, tags=["标签0", "标签1"])
        assert fig is not None

    def test_tag_filter_no_match(self, visualizer: Visualizer):
        """标签无匹配时应返回 None。"""
        records = _make_records(5)
        fig = visualizer.render_pie_chart(records, tags=["不存在的标签"])
        assert fig is None

    def test_timeline_with_tag_filter(self, visualizer: Visualizer):
        """时间线也应支持标签筛选。"""
        records = _make_records(5)
        # 只匹配 1 条 → 数据不足，不抛异常
        visualizer.render_timeline(records, tags=["标签0"])

    def test_combined_filters(self, visualizer: Visualizer):
        """时间范围 + 标签组合筛选。"""
        import matplotlib
        matplotlib.use("Agg")
        base = datetime(2024, 1, 1)
        records = _make_records(10, base_time=base)

        # 前 5 天 + 标签0 和 标签2 → 2 条（标签0=day0, 标签2=day2）
        fig = visualizer.render_pie_chart(
            records,
            start_time=base,
            end_time=base + timedelta(days=4),
            tags=["标签0", "标签2"],
        )
        assert fig is not None
