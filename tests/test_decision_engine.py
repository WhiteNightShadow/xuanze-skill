# 选择.Skill — PromptBuilder + ResponseParser 单元测试
"""
测试 PromptBuilder 的模板加载和 Prompt 组装功能，
以及 ResponseParser 的 JSON 提取和 DecisionReport 解析功能。

Requirements: R8.1, R8.3, R9.1, R9.2, R9.3, R10.1, R10.2, R10.3, R10.4
"""

import json
import tempfile
from pathlib import Path

import pytest

from xuanze_core.decision_engine import PromptBuilder, ResponseParser
from xuanze_core.models import (
    DecisionType,
    PersonalityAssessment,
    PreferenceTag,
    UserProfile,
)


# ── 辅助工厂 ──────────────────────────────────────────────


def _make_profile(**kwargs) -> UserProfile:
    """创建测试用 UserProfile"""
    defaults = {"age": 25, "city": "北京", "occupation": "工程师"}
    defaults.update(kwargs)
    return UserProfile(**defaults)


def _make_personality(**kwargs) -> PersonalityAssessment:
    """创建测试用 PersonalityAssessment"""
    return PersonalityAssessment(**kwargs)


def _make_tags() -> list[PreferenceTag]:
    """创建测试用偏好标签列表"""
    return [
        PreferenceTag(name="注重性价比", score=6.0, decision_count=3),
        PreferenceTag(name="重视健康", score=4.5, decision_count=2),
    ]


def _valid_report_json(**overrides) -> str:
    """生成有效的 DecisionReport JSON 字符串"""
    data = {
        "question_summary": "测试问题",
        "recommended_options": [
            {
                "name": "选项A",
                "reasoning": "理由A",
                "pros": ["优势1"],
                "cons": ["劣势1"],
            }
        ],
        "personalized_suggestions": "个性化建议",
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


# ── PromptBuilder.load_prompt_template 测试 ───────────────


class TestPromptBuilderLoadTemplate:
    """测试 PromptBuilder.load_prompt_template"""

    def test_load_long_term_template(self):
        """加载长期决策模板成功"""
        builder = PromptBuilder()
        template = builder.load_prompt_template(DecisionType.LONG_TERM)
        assert isinstance(template, str)
        assert len(template) > 0
        assert "{question}" in template

    def test_load_short_term_template(self):
        """加载短期决策模板成功"""
        builder = PromptBuilder()
        template = builder.load_prompt_template(DecisionType.SHORT_TERM)
        assert isinstance(template, str)
        assert len(template) > 0
        assert "{question}" in template

    def test_missing_template_raises_error(self):
        """模板文件不存在时抛出 FileNotFoundError"""
        builder = PromptBuilder(prompts_dir="/nonexistent/path")
        with pytest.raises(FileNotFoundError):
            builder.load_prompt_template(DecisionType.LONG_TERM)


# ── PromptBuilder.build_prompt 测试 ───────────────────────


class TestPromptBuilderBuildPrompt:
    """测试 PromptBuilder.build_prompt"""

    TEMPLATE = (
        "画像: {user_profile}\n"
        "偏好: {preference_tags}\n"
        "历史: {history_summary}\n"
        "搜索: {web_research}\n"
        "问题: {question}"
    )

    def test_question_included(self):
        """问题文本出现在组装后的 Prompt 中"""
        builder = PromptBuilder()
        prompt = builder.build_prompt(
            template=self.TEMPLATE,
            question="考研还是工作？",
            profile=_make_profile(),
            personality=_make_personality(),
            research_summary="搜索结果",
            preference_tags=_make_tags(),
            history_summary="历史摘要",
        )
        assert "考研还是工作？" in prompt

    def test_preference_tags_included(self):
        """偏好标签出现在组装后的 Prompt 中"""
        builder = PromptBuilder()
        tags = _make_tags()
        prompt = builder.build_prompt(
            template=self.TEMPLATE,
            question="测试问题",
            profile=_make_profile(),
            personality=_make_personality(),
            research_summary="搜索结果",
            preference_tags=tags,
            history_summary="历史摘要",
        )
        assert "注重性价比" in prompt
        assert "重视健康" in prompt

    def test_empty_tags_shows_no_preference(self):
        """空偏好标签时显示"暂无偏好数据"提示"""
        builder = PromptBuilder()
        prompt = builder.build_prompt(
            template=self.TEMPLATE,
            question="测试问题",
            profile=_make_profile(),
            personality=_make_personality(),
            research_summary="搜索结果",
            preference_tags=[],
            history_summary="历史摘要",
        )
        assert "暂无偏好数据" in prompt

    def test_empty_research_shows_no_results(self):
        """空搜索结果时显示"无联网搜索结果"提示"""
        builder = PromptBuilder()
        prompt = builder.build_prompt(
            template=self.TEMPLATE,
            question="测试问题",
            profile=_make_profile(),
            personality=_make_personality(),
            research_summary="",
            preference_tags=_make_tags(),
            history_summary="历史摘要",
        )
        assert "无联网搜索结果" in prompt


# ── ResponseParser.parse 测试 ─────────────────────────────


class TestResponseParserParse:
    """测试 ResponseParser.parse"""

    def test_valid_json(self):
        """解析有效 JSON 返回 DecisionReport"""
        response = _valid_report_json()
        report = ResponseParser.parse(response, DecisionType.LONG_TERM)
        assert report.question_summary == "测试问题"
        assert len(report.recommended_options) == 1

    def test_markdown_wrapped_json(self):
        """解析 markdown 代码块包裹的 JSON"""
        raw_json = _valid_report_json()
        response = f"```json\n{raw_json}\n```"
        report = ResponseParser.parse(response, DecisionType.SHORT_TERM)
        assert report.question_summary == "测试问题"

    def test_generic_code_block_json(self):
        """解析通用 ``` 代码块包裹的 JSON"""
        raw_json = _valid_report_json()
        response = f"```\n{raw_json}\n```"
        report = ResponseParser.parse(response, DecisionType.LONG_TERM)
        assert report.question_summary == "测试问题"

    def test_invalid_json_raises_value_error(self):
        """无效 JSON 抛出 ValueError"""
        with pytest.raises(ValueError, match="无法从响应中解析"):
            ResponseParser.parse("这不是JSON", DecisionType.LONG_TERM)

    def test_classification_set_correctly(self):
        """classification 字段设置为传入的 decision_type"""
        response = _valid_report_json()
        report_lt = ResponseParser.parse(response, DecisionType.LONG_TERM)
        assert report_lt.classification == DecisionType.LONG_TERM

        report_st = ResponseParser.parse(response, DecisionType.SHORT_TERM)
        assert report_st.classification == DecisionType.SHORT_TERM

    def test_options_capped_at_3(self):
        """推荐选项超过 3 个时截断为 3 个"""
        options = [
            {"name": f"选项{i}", "reasoning": "理由", "pros": ["优"], "cons": ["劣"]}
            for i in range(5)
        ]
        response = _valid_report_json(recommended_options=options)
        report = ResponseParser.parse(response, DecisionType.LONG_TERM)
        assert len(report.recommended_options) == 3
        assert report.recommended_options[0].name == "选项0"
        assert report.recommended_options[2].name == "选项2"
