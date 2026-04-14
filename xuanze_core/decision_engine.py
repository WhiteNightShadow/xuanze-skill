# 选择.Skill — Prompt 构建器 + 响应解析器
"""
PromptBuilder 负责加载 Prompt 模板并组装完整的分析指引 prompt。
ResponseParser 负责将 Agent 的文本输出解析为结构化 DecisionReport。

不包含 LLM 调用、联网搜索或问题分类逻辑——
这些均由宿主 Agent 自身完成。

Requirements: R8.1, R8.2, R8.3, R9.1, R9.2, R9.3, R9.4, R9.5,
             R10.1, R10.2, R10.3, R10.4, R19.1, R19.2, R19.3, R19.4
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from xuanze_core.models import (
    DecisionReport,
    DecisionType,
    PersonalityAssessment,
    PreferenceTag,
    UserProfile,
)

logger = logging.getLogger(__name__)

# 默认 prompts 目录：项目根目录下的 prompts/
DEFAULT_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class PromptBuilder:
    """Prompt 构建器

    负责加载 Prompt 模板并组装完整的分析指引 prompt，
    包含用户画像、偏好标签、历史摘要和搜索结果。

    Args:
        prompts_dir: Prompt 模板目录路径，默认为项目根目录下的 prompts/
    """

    def __init__(self, prompts_dir: str | Path | None = None) -> None:
        self.prompts_dir = Path(prompts_dir) if prompts_dir else DEFAULT_PROMPTS_DIR

    # ── Prompt 模板加载 ───────────────────────────────────

    def load_prompt_template(self, decision_type: DecisionType) -> str:
        """加载对应决策类型的 Prompt 模板。

        Args:
            decision_type: 决策类型（长期/短期）

        Returns:
            Prompt 模板文本内容

        Raises:
            FileNotFoundError: 模板文件不存在时抛出描述性错误
        """
        template_filename = (
            "long_term.txt"
            if decision_type == DecisionType.LONG_TERM
            else "short_term.txt"
        )
        template_path = self.prompts_dir / template_filename

        if not template_path.exists():
            raise FileNotFoundError(
                f"Prompt 模板文件不存在: {template_path}，"
                f"请确保 prompts/ 目录下包含 {template_filename}"
            )

        content = template_path.read_text(encoding="utf-8")
        logger.info("已加载 Prompt 模板: %s", template_filename)
        return content

    # ── Prompt 构建 ───────────────────────────────────────

    def build_prompt(
        self,
        template: str,
        question: str,
        profile: UserProfile,
        personality: PersonalityAssessment,
        research_summary: str,
        preference_tags: list[PreferenceTag],
        history_summary: str,
    ) -> str:
        """组装完整 Prompt，包含用户画像、偏好标签、历史摘要、联网搜索结果。

        将模板中的占位符替换为实际数据。对于新用户（无偏好数据），
        偏好标签区域会标注"暂无偏好数据"，使用标准推荐逻辑。

        Args:
            template: Prompt 模板文本
            question: 用户决策问题
            profile: 用户画像
            personality: 人格评估数据
            research_summary: 联网搜索结果摘要（由宿主 Agent 提供）
            preference_tags: 偏好标签列表
            history_summary: 历史决策摘要

        Returns:
            组装完成的完整 Prompt 文本
        """
        # 格式化用户画像信息
        profile_text = self.format_profile(profile, personality)

        # 格式化偏好标签（仅包含已确立偏好）
        preference_text = self.format_preference_tags(preference_tags)

        # 格式化联网搜索结果
        research_text = research_summary if research_summary else "无联网搜索结果"

        # 格式化历史摘要
        history_text = history_summary if history_summary else "暂无相关历史决策记录"

        # 替换模板占位符
        prompt = template.format(
            user_profile=profile_text,
            preference_tags=preference_text,
            history_summary=history_text,
            web_research=research_text,
            question=question,
        )

        return prompt

    # ── 格式化辅助方法 ───────────────────────────────────

    def format_profile(
        self, profile: UserProfile, personality: PersonalityAssessment
    ) -> str:
        """格式化用户画像和人格评估为文本。

        Args:
            profile: 用户画像
            personality: 人格评估数据

        Returns:
            格式化后的画像文本
        """
        parts: list[str] = []

        # 基础信息
        if profile.age:
            parts.append(f"年龄: {profile.age}")
        if profile.gender:
            parts.append(f"性别: {profile.gender}")
        if profile.city:
            parts.append(f"城市: {profile.city}")
        if profile.occupation:
            parts.append(f"职业: {profile.occupation}")
        if profile.hobbies:
            parts.append(f"爱好: {', '.join(profile.hobbies)}")
        if profile.health_conditions:
            parts.append(f"健康状况: {', '.join(profile.health_conditions)}")
        if profile.value_orientation:
            parts.append(f"价值观: {profile.value_orientation}")
        if profile.height:
            parts.append(f"身高: {profile.height}cm")
        if profile.weight:
            parts.append(f"体重: {profile.weight}kg")

        # 自定义字段
        for key, value in profile.custom_fields.items():
            parts.append(f"{key}: {value}")

        # 人格信息
        if personality.mbti_type:
            parts.append(f"MBTI: {personality.mbti_type.value}")
        if personality.zodiac_sign:
            parts.append(f"星座: {personality.zodiac_sign}")
        if personality.chinese_zodiac:
            parts.append(f"生肖: {personality.chinese_zodiac}")
        if personality.blood_type:
            parts.append(f"血型: {personality.blood_type}")
        if personality.personality_tags:
            parts.append(f"性格标签: {', '.join(personality.personality_tags)}")

        if not parts:
            return "暂无用户画像信息（新用户）"

        return "\n".join(parts)

    def format_preference_tags(self, tags: list[PreferenceTag]) -> str:
        """格式化偏好标签为文本。

        仅展示已确立偏好（由调用方传入已过滤的列表）。
        新用户无偏好数据时返回提示文本。

        Args:
            tags: 已确立的偏好标签列表

        Returns:
            格式化后的偏好标签文本
        """
        if not tags:
            return "暂无偏好数据（新用户），请基于用户画像和客观信息给出均衡推荐"

        lines: list[str] = []
        for tag in sorted(tags, key=lambda t: t.score, reverse=True):
            lines.append(f"- {tag.name}（评分: {tag.score:.1f}，决策次数: {tag.decision_count}）")

        return "\n".join(lines)


class ResponseParser:
    """响应解析器

    将宿主 Agent 的文本输出解析为结构化 DecisionReport。
    支持从 markdown 代码块中提取 JSON。
    """

    @staticmethod
    def parse(response: str, decision_type: DecisionType) -> DecisionReport:
        """解析 Agent 的决策分析文本为 DecisionReport。

        Args:
            response: Agent 输出的文本（可能包含 markdown 代码块）
            decision_type: 决策类型

        Returns:
            DecisionReport: 解析后的决策报告，classification 设为 decision_type

        Raises:
            ValueError: JSON 提取或 Pydantic 校验失败时抛出
        """
        try:
            json_str = ResponseParser.extract_json(response)
            data = json.loads(json_str)
        except (json.JSONDecodeError, Exception) as exc:
            raise ValueError(f"无法从响应中解析 JSON: {exc}") from exc

        # 设置分类字段
        data["classification"] = decision_type.value

        # 截断推荐选项至最多 3 个
        if "recommended_options" in data and len(data["recommended_options"]) > 3:
            data["recommended_options"] = data["recommended_options"][:3]

        try:
            report = DecisionReport.model_validate(data)
        except Exception as exc:
            raise ValueError(f"DecisionReport 校验失败: {exc}") from exc

        return report

    @staticmethod
    def extract_json(text: str) -> str:
        """从文本中提取 JSON 内容，支持 markdown 代码块。

        Args:
            text: 可能包含 markdown 代码块的文本

        Returns:
            提取出的 JSON 字符串
        """
        # 尝试提取 ```json ... ``` 代码块
        if "```json" in text:
            start = text.index("```json") + len("```json")
            end = text.index("```", start)
            return text[start:end].strip()

        # 尝试提取通用 ``` ... ``` 代码块
        if "```" in text:
            start = text.index("```") + len("```")
            end = text.index("```", start)
            return text[start:end].strip()

        # 兜底：尝试找到最外层 JSON 对象的花括号
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            return text[brace_start : brace_end + 1]

        # 无法提取时返回原始文本
        return text.strip()
