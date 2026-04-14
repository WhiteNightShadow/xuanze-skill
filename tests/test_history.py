# 选择.Skill — History_Manager 单元测试
"""
测试历史记录管理器的追加、查询、相关历史检索和损坏行处理。

Requirements: R12.1, R12.2, R12.3, R12.4, R12.5
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from xuanze_core.history import HistoryManager, _compute_relevance, _extract_keywords
from xuanze_core.models import (
    DecisionReport,
    DecisionType,
    HistoryRecord,
    RecommendedOption,
)


# ── 测试辅助工具 ──────────────────────────────────────────


def _make_option(name: str = "选项A") -> RecommendedOption:
    return RecommendedOption(
        name=name,
        reasoning="理由",
        pros=["优势1"],
        cons=["劣势1"],
    )


def _make_report(
    summary: str = "午餐吃什么",
    classification: DecisionType = DecisionType.SHORT_TERM,
) -> DecisionReport:
    return DecisionReport(
        question_summary=summary,
        classification=classification,
        recommended_options=[_make_option()],
        personalized_suggestions="建议",
    )


def _make_record(
    summary: str = "午餐吃什么",
    classification: DecisionType = DecisionType.SHORT_TERM,
    tags: list[str] | None = None,
    timestamp: datetime | None = None,
) -> HistoryRecord:
    report = _make_report(summary, classification)
    return HistoryRecord(
        report=report,
        classification=classification,
        tags=tags or [],
        timestamp=timestamp or datetime.now(),
    )


@pytest.fixture()
def cache_dir(tmp_path: Path) -> Path:
    """创建临时缓存目录结构"""
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    (history_dir / "long_term.jsonl").touch()
    (history_dir / "short_term.jsonl").touch()
    return tmp_path


@pytest.fixture()
def manager(cache_dir: Path) -> HistoryManager:
    return HistoryManager(cache_dir=str(cache_dir))


# ── append_record 测试 ────────────────────────────────────


class TestAppendRecord:
    def test_append_short_term(self, manager: HistoryManager, cache_dir: Path) -> None:
        """追加短期记录到 short_term.jsonl"""
        record = _make_record(classification=DecisionType.SHORT_TERM)
        manager.append_record(record)

        filepath = cache_dir / "history" / "short_term.jsonl"
        lines = filepath.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        # 验证可反序列化
        parsed = HistoryRecord.model_validate_json(lines[0])
        assert parsed.report.question_summary == "午餐吃什么"

    def test_append_long_term(self, manager: HistoryManager, cache_dir: Path) -> None:
        """追加长期记录到 long_term.jsonl"""
        record = _make_record(
            summary="志愿填报", classification=DecisionType.LONG_TERM
        )
        manager.append_record(record)

        filepath = cache_dir / "history" / "long_term.jsonl"
        lines = filepath.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

    def test_append_multiple(self, manager: HistoryManager, cache_dir: Path) -> None:
        """多次追加不覆盖已有记录"""
        for i in range(3):
            record = _make_record(summary=f"问题{i}")
            manager.append_record(record)

        filepath = cache_dir / "history" / "short_term.jsonl"
        lines = filepath.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3


# ── query_records 测试 ────────────────────────────────────


class TestQueryRecords:
    def test_query_all(self, manager: HistoryManager) -> None:
        """查询所有记录"""
        manager.append_record(_make_record(classification=DecisionType.SHORT_TERM))
        manager.append_record(
            _make_record(summary="志愿", classification=DecisionType.LONG_TERM)
        )

        results = manager.query_records()
        assert len(results) == 2

    def test_query_by_type(self, manager: HistoryManager) -> None:
        """按决策类型筛选"""
        manager.append_record(_make_record(classification=DecisionType.SHORT_TERM))
        manager.append_record(
            _make_record(summary="志愿", classification=DecisionType.LONG_TERM)
        )

        short = manager.query_records(decision_type=DecisionType.SHORT_TERM)
        assert len(short) == 1
        assert short[0].classification == DecisionType.SHORT_TERM

    def test_query_by_time_range(self, manager: HistoryManager) -> None:
        """按时间范围筛选"""
        now = datetime.now()
        old = now - timedelta(days=10)
        recent = now - timedelta(hours=1)

        manager.append_record(_make_record(summary="旧记录", timestamp=old))
        manager.append_record(_make_record(summary="新记录", timestamp=recent))

        # 只查最近 2 天
        results = manager.query_records(start_time=now - timedelta(days=2))
        assert len(results) == 1
        assert results[0].report.question_summary == "新记录"

    def test_query_by_tags(self, manager: HistoryManager) -> None:
        """按标签筛选"""
        manager.append_record(_make_record(tags=["美食", "午餐"]))
        manager.append_record(_make_record(summary="志愿填报", tags=["教育"]))

        results = manager.query_records(tags=["美食"])
        assert len(results) == 1
        assert "美食" in results[0].tags

    def test_query_tags_match_summary(self, manager: HistoryManager) -> None:
        """标签匹配也检查问题摘要"""
        manager.append_record(_make_record(summary="午餐吃什么好", tags=[]))

        results = manager.query_records(tags=["午餐"])
        assert len(results) == 1

    def test_query_sorted_by_timestamp(self, manager: HistoryManager) -> None:
        """结果按时间戳升序排列"""
        now = datetime.now()
        manager.append_record(_make_record(summary="第二", timestamp=now))
        manager.append_record(
            _make_record(summary="第一", timestamp=now - timedelta(hours=1))
        )

        results = manager.query_records()
        assert results[0].report.question_summary == "第一"
        assert results[1].report.question_summary == "第二"


# ── 损坏行处理测试 ────────────────────────────────────────


class TestCorruptedLines:
    def test_skip_corrupted_lines(
        self, manager: HistoryManager, cache_dir: Path
    ) -> None:
        """损坏行被跳过，有效记录正常加载"""
        filepath = cache_dir / "history" / "short_term.jsonl"

        # 写入一条有效记录
        valid_record = _make_record()
        valid_line = valid_record.model_dump_json()

        # 写入损坏行 + 有效行 + 损坏行
        filepath.write_text(
            "这不是有效的JSON\n" + valid_line + "\n" + "{broken json}\n",
            encoding="utf-8",
        )

        results = manager.query_records(decision_type=DecisionType.SHORT_TERM)
        assert len(results) == 1

    def test_skip_empty_lines(
        self, manager: HistoryManager, cache_dir: Path
    ) -> None:
        """空行被跳过"""
        filepath = cache_dir / "history" / "short_term.jsonl"
        valid_record = _make_record()
        filepath.write_text(
            "\n\n" + valid_record.model_dump_json() + "\n\n",
            encoding="utf-8",
        )

        results = manager.query_records(decision_type=DecisionType.SHORT_TERM)
        assert len(results) == 1

    def test_all_corrupted(
        self, manager: HistoryManager, cache_dir: Path
    ) -> None:
        """全部损坏时返回空列表"""
        filepath = cache_dir / "history" / "short_term.jsonl"
        filepath.write_text("bad1\nbad2\nbad3\n", encoding="utf-8")

        results = manager.query_records(decision_type=DecisionType.SHORT_TERM)
        assert results == []


# ── get_related_history 测试 ──────────────────────────────


class TestGetRelatedHistory:
    def test_related_by_keyword(self, manager: HistoryManager) -> None:
        """通过关键词匹配相关记录"""
        manager.append_record(_make_record(summary="午餐吃什么好"))
        manager.append_record(
            _make_record(summary="志愿填报选哪个", classification=DecisionType.LONG_TERM)
        )

        # "午餐 推荐" 分词后 "午餐" 匹配第一条记录
        results = manager.get_related_history("午餐 推荐")
        assert len(results) >= 1
        assert results[0].report.question_summary == "午餐吃什么好"

    def test_limit_results(self, manager: HistoryManager) -> None:
        """limit 参数限制返回数量"""
        for i in range(10):
            manager.append_record(_make_record(summary=f"问题{i}"))

        results = manager.get_related_history("问题", limit=3)
        assert len(results) == 3

    def test_empty_history(self, manager: HistoryManager) -> None:
        """空历史返回空列表"""
        results = manager.get_related_history("任何问题")
        assert results == []


# ── 辅助函数测试 ──────────────────────────────────────────


class TestHelpers:
    def test_extract_keywords(self) -> None:
        """关键词提取过滤短词"""
        keywords = _extract_keywords("午餐 吃 什么 好吃的")
        assert "午餐" in keywords
        assert "好吃的" in keywords
        # 单字 "吃" 和 "什么" 长度 >= 2 的会保留
        assert "什么" in keywords

    def test_extract_keywords_empty(self) -> None:
        """空文本返回空列表"""
        assert _extract_keywords("") == []

    def test_compute_relevance(self) -> None:
        """相关度计算基于关键词匹配"""
        record = _make_record(summary="午餐吃什么好", tags=["美食"])
        score = _compute_relevance(record, ["午餐", "美食"])
        assert score == 2.0

    def test_compute_relevance_no_match(self) -> None:
        """无匹配关键词得分为 0"""
        record = _make_record(summary="志愿填报")
        score = _compute_relevance(record, ["午餐"])
        assert score == 0.0
