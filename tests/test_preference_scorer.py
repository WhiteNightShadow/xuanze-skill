# Preference_Scorer 单元测试
"""
测试 PreferenceScorer 的标签提取、评分更新、衰减和阈值判断逻辑。
Requirements: R21.1, R21.2, R21.3, R21.4, R21.5, R21.6
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from xuanze_core.models import (
    DecisionReport,
    DecisionType,
    PreferenceTag,
    RecommendedOption,
    UserProfile,
)
from xuanze_core.preference_scorer import PreferenceScorer
from xuanze_core.profile_manager import ProfileManager


@pytest.fixture
def cache_dir(tmp_path):
    return tmp_path


@pytest.fixture
def pm(cache_dir):
    mgr = ProfileManager(cache_dir=str(cache_dir))
    # 初始化一个空的 profile.json
    mgr.save_profile(UserProfile())
    return mgr


@pytest.fixture
def scorer(pm):
    return PreferenceScorer(profile_manager=pm)


def _make_report(
    *,
    summary: str = "午餐选择",
    options: list[dict] | None = None,
    suggestions: str = "",
) -> DecisionReport:
    """辅助函数：快速构建 DecisionReport"""
    if options is None:
        options = [
            {
                "name": "选项A",
                "reasoning": "性价比高",
                "pros": ["便宜", "实惠"],
                "cons": ["口味一般"],
            }
        ]
    recommended = [
        RecommendedOption(
            name=o["name"],
            reasoning=o["reasoning"],
            pros=o["pros"],
            cons=o["cons"],
        )
        for o in options
    ]
    return DecisionReport(
        question_summary=summary,
        classification=DecisionType.SHORT_TERM,
        recommended_options=recommended,
        personalized_suggestions=suggestions,
    )


# ── extract_tags ──────────────────────────────────────────


class TestExtractTags:
    """测试从决策报告中提取偏好标签"""

    def test_extract_cost_related_tags(self, scorer):
        """包含性价比关键词时提取到 '注重性价比' 标签"""
        report = _make_report(
            options=[{
                "name": "经济套餐",
                "reasoning": "性价比很高",
                "pros": ["价格便宜"],
                "cons": [],
            }]
        )
        tags = scorer.extract_tags(report)
        assert "注重性价比" in tags

    def test_extract_health_related_tags(self, scorer):
        """包含健康关键词时提取到 '重视健康' 标签"""
        report = _make_report(
            suggestions="建议选择营养均衡的健康餐"
        )
        tags = scorer.extract_tags(report)
        assert "重视健康" in tags

    def test_extract_multiple_tags(self, scorer):
        """同时匹配多个标签"""
        report = _make_report(
            options=[{
                "name": "健康沙拉",
                "reasoning": "营养丰富且价格实惠",
                "pros": ["健康", "便宜"],
                "cons": [],
            }]
        )
        tags = scorer.extract_tags(report)
        assert "注重性价比" in tags
        assert "重视健康" in tags

    def test_extract_no_tags_when_no_keywords(self, scorer):
        """无匹配关键词时返回空列表"""
        report = _make_report(
            options=[{
                "name": "选项X",
                "reasoning": "一般推荐",
                "pros": ["不错"],
                "cons": ["还行"],
            }]
        )
        tags = scorer.extract_tags(report)
        assert tags == []


# ── clamp_score_change ────────────────────────────────────


class TestClampScoreChange:
    """测试评分变化限制"""

    def test_clamp_within_range(self, scorer):
        """范围内的值不变"""
        assert scorer.clamp_score_change(0.5) == 0.5
        assert scorer.clamp_score_change(-0.5) == -0.5

    def test_clamp_upper_bound(self, scorer):
        """超过上限时截断为 1.0"""
        assert scorer.clamp_score_change(2.5) == 1.0
        assert scorer.clamp_score_change(100.0) == 1.0

    def test_clamp_lower_bound(self, scorer):
        """低于下限时截断为 -1.0"""
        assert scorer.clamp_score_change(-3.0) == -1.0
        assert scorer.clamp_score_change(-100.0) == -1.0

    def test_clamp_boundary_values(self, scorer):
        """边界值保持不变"""
        assert scorer.clamp_score_change(1.0) == 1.0
        assert scorer.clamp_score_change(-1.0) == -1.0
        assert scorer.clamp_score_change(0.0) == 0.0


# ── update_scores ─────────────────────────────────────────


class TestUpdateScores:
    """测试偏好标签评分更新"""

    def test_new_tag_created(self, scorer):
        """匹配到新标签时自动创建"""
        report = _make_report(
            options=[{
                "name": "经济套餐",
                "reasoning": "性价比高",
                "pros": ["便宜"],
                "cons": [],
            }]
        )
        updated = scorer.update_scores(report, [])
        names = [t.name for t in updated]
        assert "注重性价比" in names
        tag = next(t for t in updated if t.name == "注重性价比")
        assert tag.score == 1.0
        assert tag.decision_count == 1

    def test_existing_tag_incremented(self, scorer):
        """已有标签评分递增"""
        existing = PreferenceTag(name="注重性价比", score=3.0, decision_count=3)
        report = _make_report(
            options=[{
                "name": "便宜货",
                "reasoning": "价格低",
                "pros": ["实惠"],
                "cons": [],
            }]
        )
        updated = scorer.update_scores(report, [existing])
        tag = next(t for t in updated if t.name == "注重性价比")
        assert tag.score == 4.0
        assert tag.decision_count == 4

    def test_unmatched_existing_tags_preserved(self, scorer):
        """未匹配的现有标签保持不变"""
        existing = PreferenceTag(name="偏好稳定", score=2.0, decision_count=2)
        report = _make_report(
            options=[{
                "name": "经济套餐",
                "reasoning": "性价比高",
                "pros": ["便宜"],
                "cons": [],
            }]
        )
        updated = scorer.update_scores(report, [existing])
        stable_tag = next(t for t in updated if t.name == "偏好稳定")
        assert stable_tag.score == 2.0
        assert stable_tag.decision_count == 2


# ── apply_decay ───────────────────────────────────────────


class TestApplyDecay:
    """测试时间衰减"""

    def test_recent_tag_minimal_decay(self, scorer):
        """刚更新的标签几乎不衰减"""
        tag = PreferenceTag(
            name="测试标签",
            score=10.0,
            last_updated=datetime.now(),
            decision_count=5,
        )
        decayed = scorer.apply_decay([tag])
        # 刚更新的标签，衰减极小
        assert decayed[0].score > 9.9

    def test_old_tag_significant_decay(self, scorer):
        """很久前更新的标签衰减明显"""
        tag = PreferenceTag(
            name="旧标签",
            score=10.0,
            last_updated=datetime.now() - timedelta(days=30),
            decision_count=5,
        )
        decayed = scorer.apply_decay([tag])
        # 30 天前的标签：10.0 * 0.95^30 ≈ 2.14
        assert decayed[0].score < 5.0

    def test_decay_preserves_metadata(self, scorer):
        """衰减不改变标签名称、更新时间和决策次数"""
        original_time = datetime.now() - timedelta(days=5)
        tag = PreferenceTag(
            name="保留元数据",
            score=8.0,
            last_updated=original_time,
            decision_count=3,
        )
        decayed = scorer.apply_decay([tag])
        assert decayed[0].name == "保留元数据"
        assert decayed[0].last_updated == original_time
        assert decayed[0].decision_count == 3


# ── get_established_preferences ───────────────────────────


class TestGetEstablishedPreferences:
    """测试已确立偏好筛选"""

    def test_above_threshold(self, scorer):
        """分数 >= 阈值的标签被返回"""
        tags = [
            PreferenceTag(name="高分标签", score=6.0),
            PreferenceTag(name="低分标签", score=2.0),
        ]
        established = scorer.get_established_preferences(tags)
        assert len(established) == 1
        assert established[0].name == "高分标签"

    def test_exact_threshold(self, scorer):
        """分数恰好等于阈值的标签被返回"""
        tags = [PreferenceTag(name="边界标签", score=5.0)]
        established = scorer.get_established_preferences(tags)
        assert len(established) == 1

    def test_below_threshold(self, scorer):
        """分数低于阈值的标签不被返回"""
        tags = [PreferenceTag(name="观察中", score=4.9)]
        established = scorer.get_established_preferences(tags)
        assert len(established) == 0

    def test_custom_threshold(self, pm):
        """自定义阈值生效"""
        scorer = PreferenceScorer(profile_manager=pm, threshold=3.0)
        tags = [PreferenceTag(name="中等分数", score=3.5)]
        established = scorer.get_established_preferences(tags)
        assert len(established) == 1


# ── score_and_save 集成测试 ───────────────────────────────


class TestScoreAndSave:
    """测试完整评分流程（含 profile.json 写入）"""

    def test_score_and_save_writes_to_profile(self, scorer, pm):
        """评分后偏好标签写入 profile.json"""
        report = _make_report(
            options=[{
                "name": "健康餐",
                "reasoning": "营养均衡",
                "pros": ["健康"],
                "cons": [],
            }]
        )
        result = scorer.score_and_save(report)
        # 验证返回值包含标签
        names = [t.name for t in result]
        assert "重视健康" in names

        # 验证 profile.json 已更新
        profile = pm.load_profile()
        saved_names = [t.name for t in profile.preference_tags]
        assert "重视健康" in saved_names

    def test_score_and_save_accumulates(self, scorer, pm):
        """多次评分后分数累积"""
        report = _make_report(
            options=[{
                "name": "便宜货",
                "reasoning": "价格低",
                "pros": ["实惠"],
                "cons": [],
            }]
        )
        # 连续 3 次相同偏好的决策
        scorer.score_and_save(report)
        scorer.score_and_save(report)
        scorer.score_and_save(report)

        profile = pm.load_profile()
        tag = next(t for t in profile.preference_tags if t.name == "注重性价比")
        # 每次 +1.0，但有微小衰减，总分应接近 3.0
        assert tag.score > 2.5
        assert tag.decision_count == 3
