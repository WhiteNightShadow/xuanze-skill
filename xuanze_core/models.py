# 选择.Skill — 数据模型定义
"""
所有 Pydantic v2 数据模型，保证类型安全和 JSON round-trip 正确性。

包含：用户画像、人格评估、偏好标签、搜索结果、分类结果、
推荐选项、决策报告、历史记录、导出格式等模型定义。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


# ── 枚举类型 ──────────────────────────────────────────────
# 定义系统中使用的所有枚举常量


class MBTIType(str, Enum):
    """16 种标准 MBTI 人格类型。

    每种类型由四个维度的字母组合而成：
    E/I（外向/内向）、S/N（感觉/直觉）、T/F（思考/情感）、J/P（判断/感知）
    """

    ISTJ = "ISTJ"
    ISFJ = "ISFJ"
    INFJ = "INFJ"
    INTJ = "INTJ"
    ISTP = "ISTP"
    ISFP = "ISFP"
    INFP = "INFP"
    INTP = "INTP"
    ESTP = "ESTP"
    ESFP = "ESFP"
    ENFP = "ENFP"
    ENTP = "ENTP"
    ESTJ = "ESTJ"
    ESFJ = "ESFJ"
    ENFJ = "ENFJ"
    ENTJ = "ENTJ"


class DecisionType(str, Enum):
    """决策类型：长期选择 / 短期选择"""

    LONG_TERM = "long_term"
    SHORT_TERM = "short_term"


class ExportFormat(str, Enum):
    """导出格式"""

    MARKDOWN = "markdown"
    PDF = "pdf"
    PNG = "png"


# ── 用户画像相关模型 ──────────────────────────────────────
# 用户画像包含基础信息、人格评估和偏好标签三部分


class PersonalityAssessment(BaseModel):
    """人格评估数据

    通过内置测试题或用户自定义输入获取的人格特征。
    所有字段均为可选，用户可填写任意子集。
    """

    mbti_type: MBTIType | None = None
    zodiac_sign: str | None = None  # 星座
    chinese_zodiac: str | None = None  # 生肖
    blood_type: str | None = None  # 血型
    personality_tags: list[str] = Field(default_factory=list)  # 性格标签
    assessment_method: str = "none"  # "builtin_quiz" | "custom_input" | "none"
    assessed_at: datetime | None = None


class PreferenceTag(BaseModel):
    """选择偏好标签

    通过累积评分算法从用户历史决策中提炼出的偏好特征，
    如"注重性价比"、"偏好稳定"、"追求体验"等。
    """

    name: str  # 标签名称
    score: float = 0.0  # 累积评分
    last_updated: datetime = Field(default_factory=datetime.now)
    decision_count: int = 0  # 影响该标签的决策次数


class UserProfile(BaseModel):
    """用户画像

    包含基础个人信息和选择偏好标签。
    所有字段均为可选，用户可在引导流程中跳过任意字段。
    """

    age: int | None = None
    gender: str | None = None
    height: float | None = None  # cm
    weight: float | None = None  # kg
    city: str | None = None
    occupation: str | None = None
    health_conditions: list[str] = Field(default_factory=list)
    hobbies: list[str] = Field(default_factory=list)
    value_orientation: str | None = None  # 价值观取向
    custom_fields: dict[str, str] = Field(default_factory=dict)
    preference_tags: list[PreferenceTag] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @field_validator("age")
    @classmethod
    def validate_age(cls, v: int | None) -> int | None:
        """年龄校验：必须在 1-150 之间"""
        if v is not None and not (1 <= v <= 150):
            raise ValueError("年龄必须在 1 到 150 之间")
        return v


# ── Onboarding 数据输入模型 ───────────────────────────────
# 宿主 Agent 收集的用户数据（纯数据，无交互逻辑）


class OnboardingProfileData(BaseModel):
    """宿主 Agent 收集的用户基础信息（纯数据，无交互逻辑）

    所有字段均为可选，Agent 可提交任意子集。
    """

    age: int | None = None
    gender: str | None = None
    height: float | None = None  # cm
    weight: float | None = None  # kg
    city: str | None = None
    occupation: str | None = None
    health_conditions: list[str] = Field(default_factory=list)
    hobbies: list[str] = Field(default_factory=list)
    value_orientation: str | None = None  # 价值观取向
    custom_fields: dict[str, str] = Field(default_factory=dict)


class OnboardingPersonalityData(BaseModel):
    """宿主 Agent 收集的人格信息（纯数据，无交互逻辑）

    所有字段均为可选，Agent 可提交任意子集。
    mbti_type 为字符串输入，由 Onboarding_Module 内部校验。
    """

    mbti_type: str | None = None  # 字符串输入，内部校验
    zodiac_sign: str | None = None  # 星座
    chinese_zodiac: str | None = None  # 生肖
    blood_type: str | None = None  # 血型
    personality_tags: list[str] = Field(default_factory=list)  # 性格标签


# ── 搜索结果模型 ──────────────────────────────────────────
# 联网搜索返回的原始结果和汇总摘要


class SearchResult(BaseModel):
    """单条搜索结果"""

    title: str
    url: str
    snippet: str
    source: str = ""  # 来源标识


class ResearchResult(BaseModel):
    """联网搜索汇总结果"""

    query: str  # 搜索查询
    results: list[SearchResult] = Field(default_factory=list)
    summary: str = ""  # 摘要
    searched_at: datetime = Field(default_factory=datetime.now)


# ── 分类结果模型 ──────────────────────────────────────────
# 问题分类器的输出，包含决策类型和置信度


class ClassificationResult(BaseModel):
    """问题分类结果

    confidence 字段取值范围 [0.0, 1.0]，低于 0.6 时需请求用户确认。
    """

    decision_type: DecisionType
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


# ── 决策报告模型 ──────────────────────────────────────────
# 核心输出：包含推荐选项、优劣势对比和个性化建议


class RecommendedOption(BaseModel):
    """推荐选项

    每个选项包含名称、推荐理由、优劣势对比、风险提示和综合评分。
    """

    name: str  # 选项名称
    reasoning: str  # 推荐理由
    pros: list[str]  # 优势列表
    cons: list[str]  # 劣势列表
    risk_warnings: list[str] = Field(default_factory=list)  # 风险提示
    score: float | None = None  # 综合评分（可选）


class DecisionReport(BaseModel):
    """决策报告

    包含问题摘要、分类类型、Top 3 推荐选项、个性化建议、
    信息来源和原始 LLM 响应。recommended_options 最多 3 个。
    """

    question_summary: str  # 问题摘要
    classification: DecisionType  # 分类类型
    recommended_options: list[RecommendedOption] = Field(max_length=3)  # Top 3 推荐
    personalized_suggestions: str  # 个性化建议
    source_references: list[str] = Field(default_factory=list)  # 信息来源
    timestamp: datetime = Field(default_factory=datetime.now)
    raw_llm_response: str = ""  # 原始 LLM 响应（调试用）


# ── 历史记录模型 ──────────────────────────────────────────
# 每次决策归档时生成的完整记录，存储在 JSONL 文件中


class HistoryRecord(BaseModel):
    """历史记录条目

    包含完整的决策报告、分类类型、时间戳和关键词标签。
    """

    report: DecisionReport  # 决策报告
    classification: DecisionType  # 分类类型
    timestamp: datetime = Field(default_factory=datetime.now)
    tags: list[str] = Field(default_factory=list)  # 关键词标签
