# 选择.Skill — 统一 API 入口
"""
XuanzeSkill 是宿主 Agent 调用的统一 API 入口，
封装所有内部模块（Onboarding、ProfileManager、HistoryManager、
PreferenceScorer、PromptBuilder、ResponseParser）。

所有方法在遇到可恢复错误（缺失文件、空历史）时优雅降级，
返回空默认值而非抛出异常。

Requirements: R7.1, R7.2, R7.3, R7.4, R7.5, R7.6
"""

from __future__ import annotations

import logging
from datetime import datetime

from xuanze_core.decision_engine import PromptBuilder, ResponseParser
from xuanze_core.history import HistoryManager
from xuanze_core.models import (
    DecisionReport,
    DecisionType,
    HistoryRecord,
    OnboardingPersonalityData,
    OnboardingProfileData,
    PersonalityAssessment,
    UserProfile,
)
from xuanze_core.onboarding import OnboardingModule
from xuanze_core.preference_scorer import PreferenceScorer
from xuanze_core.profile_manager import ProfileManager

logger = logging.getLogger(__name__)

# 默认缓存目录
DEFAULT_CACHE_DIR = ".xuanze_cache"


class XuanzeSkill:
    """宿主 Agent 调用的统一 API 入口

    封装 Onboarding、画像管理、决策 Prompt 构建、响应解析、
    偏好评分和历史记录等所有功能模块。

    Args:
        cache_dir: 缓存目录路径，默认为 .xuanze_cache
    """

    def __init__(self, cache_dir: str = DEFAULT_CACHE_DIR) -> None:
        self.cache_dir = cache_dir
        self._profile_manager = ProfileManager(cache_dir)
        self._history_manager = HistoryManager(cache_dir)
        self._preference_scorer = PreferenceScorer(self._profile_manager)
        self._onboarding = OnboardingModule(cache_dir)
        self._prompt_builder = PromptBuilder()

    # ── Onboarding 方法 ──────────────────────────────────

    def initialize(self) -> None:
        """初始化缓存目录结构。

        委托给 OnboardingModule.initialize_cache()，
        创建 profile.json、personality.json 和 history/ 目录。
        """
        self._onboarding.initialize_cache()

    def save_profile(self, data: dict) -> UserProfile:
        """保存用户基础信息。

        将 dict 包装为 OnboardingProfileData，
        委托给 OnboardingModule.save_profile_data()。

        Args:
            data: 用户基础信息字典（所有字段可选）

        Returns:
            UserProfile: 合并后的完整用户画像
        """
        profile_data = OnboardingProfileData(**data)
        return self._onboarding.save_profile_data(profile_data)

    def save_personality(self, data: dict) -> PersonalityAssessment:
        """保存用户人格信息。

        将 dict 包装为 OnboardingPersonalityData，
        委托给 OnboardingModule.save_personality_data()。

        Args:
            data: 人格信息字典（所有字段可选）

        Returns:
            PersonalityAssessment: 校验后的人格评估实例

        Raises:
            ValueError: MBTI 类型无效时抛出
        """
        personality_data = OnboardingPersonalityData(**data)
        return self._onboarding.save_personality_data(personality_data)

    def get_quiz_questions(self) -> list[dict]:
        """获取 MBTI 测试题列表。

        委托给 OnboardingModule.get_mbti_quiz_questions()。

        Returns:
            list[dict]: 测试题列表
        """
        return self._onboarding.get_mbti_quiz_questions()

    def calculate_mbti(self, answers: dict[int, str]) -> str:
        """根据答案计算 MBTI 类型。

        委托给 OnboardingModule.calculate_mbti_result()。

        Args:
            answers: 题目索引 -> 方向字母 的映射

        Returns:
            str: 四字母 MBTI 类型字符串
        """
        return self._onboarding.calculate_mbti_result(answers)

    # ── 决策流程方法 ─────────────────────────────────────

    def get_prompt_template(self, decision_type: str) -> str:
        """加载对应决策类型的 Prompt 模板。

        将字符串转换为 DecisionType 枚举，委托给 PromptBuilder。

        Args:
            decision_type: 决策类型字符串（"long_term" 或 "short_term"）

        Returns:
            str: Prompt 模板文本
        """
        dt = DecisionType(decision_type)
        return self._prompt_builder.load_prompt_template(dt)

    def build_decision_prompt(
        self,
        question: str,
        decision_type: str,
        research_summary: str = "",
    ) -> str:
        """一站式 Prompt 构建：加载模板 + 画像 + 偏好 + 历史 + 搜索结果。

        在缺失画像或历史数据时优雅降级为空默认值。

        Args:
            question: 用户决策问题
            decision_type: 决策类型字符串（"long_term" 或 "short_term"）
            research_summary: 联网搜索结果摘要（可选）

        Returns:
            str: 组装完成的完整 Prompt 文本
        """
        dt = DecisionType(decision_type)

        # 加载模板
        template = self._prompt_builder.load_prompt_template(dt)

        # 加载画像（优雅降级）
        try:
            profile = self._profile_manager.load_profile()
        except Exception:
            logger.warning("加载用户画像失败，使用空默认值")
            profile = UserProfile()

        # 加载人格评估（优雅降级）
        try:
            personality = self._profile_manager.load_personality()
        except Exception:
            logger.warning("加载人格评估失败，使用空默认值")
            personality = PersonalityAssessment()

        # 获取已确立的偏好标签
        preference_tags = profile.preference_tags

        # 获取相关历史摘要（优雅降级）
        try:
            related_records = self._history_manager.get_related_history(
                question, limit=5
            )
            history_summary = self._format_history_summary(related_records)
        except Exception:
            logger.warning("加载相关历史失败，使用空摘要")
            history_summary = ""

        # 组装 Prompt
        return self._prompt_builder.build_prompt(
            template=template,
            question=question,
            profile=profile,
            personality=personality,
            research_summary=research_summary,
            preference_tags=preference_tags,
            history_summary=history_summary,
        )

    def parse_decision_response(
        self, response: str, decision_type: str
    ) -> DecisionReport:
        """解析 Agent 输出为 DecisionReport。

        将字符串转换为 DecisionType，委托给 ResponseParser.parse()。

        Args:
            response: Agent 输出的文本
            decision_type: 决策类型字符串

        Returns:
            DecisionReport: 解析后的决策报告

        Raises:
            ValueError: 解析失败时抛出
        """
        dt = DecisionType(decision_type)
        return ResponseParser.parse(response, dt)

    def finalize_decision(self, report: DecisionReport) -> None:
        """决策后处理：更新偏好评分 + 归档历史记录。

        1. 通过 PreferenceScorer 更新偏好标签评分
        2. 通过 HistoryManager 追加历史记录

        Args:
            report: 决策报告
        """
        # 更新偏好评分
        self._preference_scorer.score_and_save(report)

        # 提取标签用于历史记录
        tags = self._preference_scorer.extract_tags(report)

        # 构建历史记录并追加
        record = HistoryRecord(
            report=report,
            classification=report.classification,
            timestamp=datetime.now(),
            tags=tags,
        )
        self._history_manager.append_record(record)

    # ── 数据查询方法 ─────────────────────────────────────

    def get_profile(self) -> dict:
        """获取用户画像（含人格评估）。

        合并 profile.json 和 personality.json 数据为单个字典。
        缺失文件时优雅降级为空默认值。

        Returns:
            dict: 包含 profile 和 personality 字段的字典
        """
        # 加载画像（优雅降级）
        try:
            profile = self._profile_manager.load_profile()
            profile_dict = profile.model_dump()
        except Exception:
            logger.warning("加载用户画像失败，返回空默认值")
            profile_dict = UserProfile().model_dump()

        # 加载人格评估（优雅降级）
        try:
            personality = self._profile_manager.load_personality()
            personality_dict = personality.model_dump()
        except Exception:
            logger.warning("加载人格评估失败，返回空默认值")
            personality_dict = PersonalityAssessment().model_dump()

        return {
            "profile": profile_dict,
            "personality": personality_dict,
        }

    def get_history(
        self, decision_type: str | None = None, limit: int = 10
    ) -> list[dict]:
        """查询历史记录。

        委托给 HistoryManager.query_records()，返回字典列表。
        缺失历史时优雅降级为空列表。

        Args:
            decision_type: 决策类型过滤（None 表示查询所有类型）
            limit: 最多返回的记录数

        Returns:
            list[dict]: 历史记录字典列表
        """
        try:
            dt = DecisionType(decision_type) if decision_type else None
            records = self._history_manager.query_records(decision_type=dt)
            # 取最近 limit 条（query_records 返回升序，取末尾）
            limited = records[-limit:] if len(records) > limit else records
            return [r.model_dump() for r in limited]
        except Exception:
            logger.warning("查询历史记录失败，返回空列表")
            return []

    def get_related_history(
        self, question: str, limit: int = 5
    ) -> list[dict]:
        """获取与当前问题相关的历史记录。

        委托给 HistoryManager.get_related_history()，返回字典列表。
        缺失历史时优雅降级为空列表。

        Args:
            question: 当前决策问题文本
            limit: 最多返回的记录数

        Returns:
            list[dict]: 相关历史记录字典列表
        """
        try:
            records = self._history_manager.get_related_history(
                question, limit=limit
            )
            return [r.model_dump() for r in records]
        except Exception:
            logger.warning("获取相关历史失败，返回空列表")
            return []

    def get_preference_tags(self) -> list[dict]:
        """获取用户偏好标签列表。

        从 profile.json 中读取 preference_tags 字段，返回字典列表。
        缺失数据时优雅降级为空列表。

        Returns:
            list[dict]: 偏好标签字典列表
        """
        try:
            profile = self._profile_manager.load_profile()
            return [tag.model_dump() for tag in profile.preference_tags]
        except Exception:
            logger.warning("获取偏好标签失败，返回空列表")
            return []

    # ── 内部辅助方法 ─────────────────────────────────────

    @staticmethod
    def _format_history_summary(records: list[HistoryRecord]) -> str:
        """将历史记录列表格式化为文本摘要。

        Args:
            records: 历史记录列表

        Returns:
            str: 格式化后的历史摘要文本
        """
        if not records:
            return ""

        lines: list[str] = []
        for record in records:
            ts = record.timestamp.strftime("%Y-%m-%d")
            summary = record.report.question_summary
            top_option = (
                record.report.recommended_options[0].name
                if record.report.recommended_options
                else "无推荐"
            )
            lines.append(f"- [{ts}] {summary} → 推荐: {top_option}")

        return "\n".join(lines)
