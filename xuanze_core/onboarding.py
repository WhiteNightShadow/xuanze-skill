# 选择.Skill — 首次加载引导模块
"""
Onboarding_Module 负责缓存目录初始化和用户画像数据保存。
作为纯数据 API 模块，不包含任何用户交互逻辑——
所有对话交互由宿主 Agent 通过 SKILL.md 编排完成。

Requirements: R1.1, R1.2, R1.3, R2.1, R2.2, R2.3, R2.4,
             R3.1, R3.2, R3.3, R3.4, R4.1, R4.2, R4.5, R9.4
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from xuanze_core.models import (
    MBTIType,
    OnboardingPersonalityData,
    OnboardingProfileData,
    PersonalityAssessment,
    UserProfile,
)
from xuanze_core.profile_manager import ProfileManager

logger = logging.getLogger(__name__)

# 默认缓存目录
DEFAULT_CACHE_DIR = ".xuanze_cache"

# MBTI 测试题文件路径
MBTI_QUIZ_PATH = Path("prompts/mbti_quiz.json")

# 有效 MBTI 类型集合（用于快速校验）
VALID_MBTI_TYPES: set[str] = {t.value for t in MBTIType}


class OnboardingError(Exception):
    """引导流程异常基类"""


class OnboardingModule:
    """首次加载引导模块（纯数据 API）

    负责创建缓存目录结构、接收 Agent 收集的用户数据并保存。
    不包含任何用户交互逻辑。

    Args:
        cache_dir: 缓存目录路径，默认为 .xuanze_cache
    """

    def __init__(self, cache_dir: str = DEFAULT_CACHE_DIR) -> None:
        self.cache_dir = Path(cache_dir)
        self.profile_manager = ProfileManager(cache_dir)

    # ── 缓存目录初始化 ───────────────────────────────────

    def initialize_cache(self) -> None:
        """创建 .xuanze_cache/ 目录结构。

        创建以下文件（若不存在）：
        - profile.json（含空 preference_tags）
        - personality.json
        - history/long_term.jsonl
        - history/short_term.jsonl

        已存在的文件会被跳过，保留现有数据。

        Raises:
            OnboardingError: 文件系统权限错误时抛出描述性错误
        """
        try:
            # 创建主目录和 history 子目录
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            history_dir = self.cache_dir / "history"
            history_dir.mkdir(parents=True, exist_ok=True)

            # profile.json — 含空 preference_tags
            profile_path = self.cache_dir / "profile.json"
            if not profile_path.exists():
                default_profile = UserProfile()
                profile_path.write_text(
                    default_profile.model_dump_json(indent=2),
                    encoding="utf-8",
                )
                logger.info("已创建 %s", profile_path)

            # personality.json
            personality_path = self.cache_dir / "personality.json"
            if not personality_path.exists():
                default_personality = PersonalityAssessment()
                personality_path.write_text(
                    default_personality.model_dump_json(indent=2),
                    encoding="utf-8",
                )
                logger.info("已创建 %s", personality_path)

            # history/long_term.jsonl
            long_term_path = history_dir / "long_term.jsonl"
            if not long_term_path.exists():
                long_term_path.touch()
                logger.info("已创建 %s", long_term_path)

            # history/short_term.jsonl
            short_term_path = history_dir / "short_term.jsonl"
            if not short_term_path.exists():
                short_term_path.touch()
                logger.info("已创建 %s", short_term_path)

        except PermissionError as exc:
            raise OnboardingError(
                f"无法创建缓存目录 '{self.cache_dir}'：权限不足。"
                f"请检查目录 '{self.cache_dir.parent.resolve()}' 的写入权限。"
                f"详细信息: {exc}"
            ) from exc
        except OSError as exc:
            raise OnboardingError(
                f"创建缓存目录 '{self.cache_dir}' 时发生文件系统错误: {exc}"
            ) from exc

    # ── 用户画像数据保存 ─────────────────────────────────

    def save_profile_data(self, data: OnboardingProfileData) -> UserProfile:
        """接收 Agent 收集的基础信息，校验并保存到 profile.json。

        与现有 profile 数据合并：新数据覆盖已有字段，
        未提供的字段保留原值。

        Args:
            data: Agent 收集的用户基础信息

        Returns:
            UserProfile: 合并后的完整用户画像
        """
        # 构建更新字典：仅包含用户实际提供的字段
        updates: dict = {}
        if data.age is not None:
            updates["age"] = data.age
        if data.gender is not None:
            updates["gender"] = data.gender
        if data.height is not None:
            updates["height"] = data.height
        if data.weight is not None:
            updates["weight"] = data.weight
        if data.city is not None:
            updates["city"] = data.city
        if data.occupation is not None:
            updates["occupation"] = data.occupation
        if data.health_conditions:
            updates["health_conditions"] = data.health_conditions
        if data.hobbies:
            updates["hobbies"] = data.hobbies
        if data.value_orientation is not None:
            updates["value_orientation"] = data.value_orientation
        if data.custom_fields:
            updates["custom_fields"] = data.custom_fields

        # 尝试加载现有 profile 并合并
        try:
            profile = self.profile_manager.load_profile()
            current_data = profile.model_dump()
            current_data.update(updates)
            updated_profile = UserProfile.model_validate(current_data)
        except FileNotFoundError:
            # 文件不存在时直接创建新 profile
            updated_profile = UserProfile(**updates)

        self.profile_manager.save_profile(updated_profile)
        return updated_profile

    # ── 人格画像数据保存 ─────────────────────────────────

    def save_personality_data(
        self, data: OnboardingPersonalityData
    ) -> PersonalityAssessment:
        """接收 Agent 收集的人格信息，校验 MBTI 类型，保存到 personality.json。

        Args:
            data: Agent 收集的人格信息

        Returns:
            PersonalityAssessment: 校验后的人格评估实例

        Raises:
            ValueError: MBTI 类型不在 16 种标准类型中时抛出
        """
        # 校验 MBTI 类型
        mbti_type: MBTIType | None = None
        if data.mbti_type is not None:
            mbti_upper = data.mbti_type.strip().upper()
            if mbti_upper not in VALID_MBTI_TYPES:
                raise ValueError(
                    f"'{data.mbti_type}' 不是有效的 MBTI 类型。"
                    f"请提供 16 种标准类型之一，如 INTJ、ENFP 等。"
                )
            mbti_type = MBTIType(mbti_upper)

        assessment = PersonalityAssessment(
            mbti_type=mbti_type,
            zodiac_sign=data.zodiac_sign,
            chinese_zodiac=data.chinese_zodiac,
            blood_type=data.blood_type,
            personality_tags=data.personality_tags,
            assessment_method="custom_input",
            assessed_at=datetime.now(),
        )

        self.profile_manager.save_personality(assessment)
        return assessment

    # ── MBTI 测试题 API ──────────────────────────────────

    def get_mbti_quiz_questions(self) -> list[dict]:
        """加载并返回 MBTI 测试题列表，供 Agent 在对话中逐题提问。

        Returns:
            list[dict]: 测试题列表，每题包含 text、options 等字段

        Raises:
            FileNotFoundError: 测试题文件不存在时抛出
            OnboardingError: 文件格式错误时抛出
        """
        if not MBTI_QUIZ_PATH.exists():
            raise FileNotFoundError(
                f"内置测试题文件不存在: {MBTI_QUIZ_PATH}。"
                "请确保 prompts/mbti_quiz.json 文件存在。"
            )

        try:
            raw = MBTI_QUIZ_PATH.read_text(encoding="utf-8")
            quiz_data = json.loads(raw)
        except (json.JSONDecodeError, OSError) as exc:
            raise OnboardingError(f"加载测试题失败: {exc}") from exc

        questions = quiz_data.get("questions", [])
        if not questions:
            raise OnboardingError("测试题文件中没有找到题目。")

        return questions

    def calculate_mbti_result(self, answers: dict[int, str]) -> str:
        """根据 Agent 收集的答案计算 MBTI 类型。

        使用多数投票法：每个维度取得分较高的方向。

        Args:
            answers: 题目索引 -> 方向字母 的映射（如 {0: "E", 1: "I", ...}）

        Returns:
            str: 四字母 MBTI 类型字符串（如 "INTJ"）
        """
        # 统计各方向得分
        scores: dict[str, int] = {}
        for direction in answers.values():
            scores[direction] = scores.get(direction, 0) + 1

        return self._calculate_mbti(scores)

    def _calculate_mbti(self, scores: dict[str, int]) -> str:
        """根据各维度方向得分计算 MBTI 类型。

        使用多数投票法：每个维度取得分较高的方向。

        Args:
            scores: 方向 -> 选择次数 的映射

        Returns:
            str: 四字母 MBTI 类型字符串
        """
        # 四个维度的对立方向
        dimensions = [
            ("E", "I"),  # 外向 vs 内向
            ("S", "N"),  # 感觉 vs 直觉
            ("T", "F"),  # 思考 vs 情感
            ("J", "P"),  # 判断 vs 感知
        ]

        result = ""
        for left, right in dimensions:
            left_score = scores.get(left, 0)
            right_score = scores.get(right, 0)
            # 得分相同时取第一个方向
            result += left if left_score >= right_score else right

        return result
