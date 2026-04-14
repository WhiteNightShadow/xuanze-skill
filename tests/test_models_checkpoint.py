# Checkpoint 2: 数据模型基础验证
"""
验证所有 Pydantic 数据模型可以正确导入、实例化，
以及关键 validator 正常工作（age、confidence、max_length）。
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from xuanze_core.models import (
    ClassificationResult,
    DecisionReport,
    DecisionType,
    ExportFormat,
    HistoryRecord,
    MBTIType,
    PersonalityAssessment,
    PreferenceTag,
    RecommendedOption,
    ResearchResult,
    SearchResult,
    UserProfile,
)


# ── 基础导入与实例化 ──────────────────────────────────────


class TestModelsImportAndInstantiation:
    """确认所有模型可以正常实例化"""

    def test_mbti_enum_has_16_types(self) -> None:
        assert len(MBTIType) == 16

    def test_decision_type_enum(self) -> None:
        assert DecisionType.LONG_TERM.value == "long_term"
        assert DecisionType.SHORT_TERM.value == "short_term"

    def test_export_format_enum(self) -> None:
        assert set(e.value for e in ExportFormat) == {"markdown", "pdf", "png"}

    def test_personality_assessment_defaults(self) -> None:
        pa = PersonalityAssessment()
        assert pa.mbti_type is None
        assert pa.assessment_method == "none"
        assert pa.personality_tags == []

    def test_preference_tag_creation(self) -> None:
        tag = PreferenceTag(name="注重性价比")
        assert tag.name == "注重性价比"
        assert tag.score == 0.0
        assert tag.decision_count == 0

    def test_user_profile_defaults(self) -> None:
        profile = UserProfile()
        assert profile.age is None
        assert profile.preference_tags == []
        assert profile.custom_fields == {}

    def test_search_result_creation(self) -> None:
        sr = SearchResult(title="Test", url="https://example.com", snippet="A snippet")
        assert sr.title == "Test"

    def test_research_result_creation(self) -> None:
        rr = ResearchResult(query="test query")
        assert rr.results == []
        assert rr.summary == ""

    def test_classification_result_creation(self) -> None:
        cr = ClassificationResult(
            decision_type=DecisionType.LONG_TERM, confidence=0.85, reasoning="test"
        )
        assert cr.confidence == 0.85

    def test_recommended_option_creation(self) -> None:
        opt = RecommendedOption(
            name="选项A", reasoning="理由", pros=["优势1"], cons=["劣势1"]
        )
        assert opt.name == "选项A"
        assert opt.score is None

    def test_decision_report_creation(self) -> None:
        opt = RecommendedOption(
            name="选项A", reasoning="理由", pros=["优势1"], cons=["劣势1"]
        )
        report = DecisionReport(
            question_summary="测试问题",
            classification=DecisionType.SHORT_TERM,
            recommended_options=[opt],
            personalized_suggestions="建议内容",
        )
        assert report.question_summary == "测试问题"
        assert len(report.recommended_options) == 1

    def test_history_record_creation(self) -> None:
        opt = RecommendedOption(
            name="选项A", reasoning="理由", pros=["优势1"], cons=["劣势1"]
        )
        report = DecisionReport(
            question_summary="测试问题",
            classification=DecisionType.LONG_TERM,
            recommended_options=[opt],
            personalized_suggestions="建议",
        )
        record = HistoryRecord(
            report=report,
            classification=DecisionType.LONG_TERM,
            tags=["测试"],
        )
        assert record.tags == ["测试"]


# ── Validator 验证 ────────────────────────────────────────


class TestValidators:
    """验证关键字段校验器正常工作"""

    # -- age validator --
    def test_age_valid(self) -> None:
        profile = UserProfile(age=25)
        assert profile.age == 25

    def test_age_boundary_low(self) -> None:
        profile = UserProfile(age=1)
        assert profile.age == 1

    def test_age_boundary_high(self) -> None:
        profile = UserProfile(age=150)
        assert profile.age == 150

    def test_age_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserProfile(age=0)

    def test_age_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserProfile(age=-1)

    def test_age_over_150_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserProfile(age=151)

    # -- confidence range --
    def test_confidence_valid(self) -> None:
        cr = ClassificationResult(
            decision_type=DecisionType.SHORT_TERM, confidence=0.5
        )
        assert cr.confidence == 0.5

    def test_confidence_zero(self) -> None:
        cr = ClassificationResult(
            decision_type=DecisionType.SHORT_TERM, confidence=0.0
        )
        assert cr.confidence == 0.0

    def test_confidence_one(self) -> None:
        cr = ClassificationResult(
            decision_type=DecisionType.SHORT_TERM, confidence=1.0
        )
        assert cr.confidence == 1.0

    def test_confidence_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ClassificationResult(
                decision_type=DecisionType.SHORT_TERM, confidence=-0.1
            )

    def test_confidence_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ClassificationResult(
                decision_type=DecisionType.SHORT_TERM, confidence=1.1
            )

    # -- recommended_options max_length=3 --
    def test_recommended_options_max_3(self) -> None:
        opts = [
            RecommendedOption(name=f"选项{i}", reasoning="r", pros=["p"], cons=["c"])
            for i in range(4)
        ]
        with pytest.raises(ValidationError):
            DecisionReport(
                question_summary="q",
                classification=DecisionType.LONG_TERM,
                recommended_options=opts,
                personalized_suggestions="s",
            )

    def test_recommended_options_exactly_3_ok(self) -> None:
        opts = [
            RecommendedOption(name=f"选项{i}", reasoning="r", pros=["p"], cons=["c"])
            for i in range(3)
        ]
        report = DecisionReport(
            question_summary="q",
            classification=DecisionType.LONG_TERM,
            recommended_options=opts,
            personalized_suggestions="s",
        )
        assert len(report.recommended_options) == 3
