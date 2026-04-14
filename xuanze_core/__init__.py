# 选择.Skill — Skill-as-Module 智能决策辅助模块
"""xuanze_core 包：被动式 Skill 模块，由宿主 LLM Agent 加载和编排。

本包提供决策辅助管道的核心组件，包括：
- XuanzeSkill: 统一 API 入口，封装所有 Agent 可调用的方法
- PromptBuilder: Prompt 构建器，加载模板并组装分析指引 prompt
- ResponseParser: 响应解析器，将 Agent 输出解析为结构化 DecisionReport
- OnboardingModule: 首次加载引导模块（纯数据 API）
- ProfileManager: 用户画像管理
- PreferenceScorer: 偏好评分算法
- HistoryManager: 历史记录管理
- Visualizer / Exporter: 可选工具模块
"""

from xuanze_core.decision_engine import PromptBuilder, ResponseParser
from xuanze_core.models import (
    ClassificationResult,
    DecisionReport,
    DecisionType,
    ExportFormat,
    HistoryRecord,
    MBTIType,
    OnboardingPersonalityData,
    OnboardingProfileData,
    PersonalityAssessment,
    PreferenceTag,
    RecommendedOption,
    ResearchResult,
    SearchResult,
    UserProfile,
)
from xuanze_core.skill_api import XuanzeSkill

__all__: list[str] = [
    # 统一 API 入口
    "XuanzeSkill",
    # Prompt 构建与响应解析
    "PromptBuilder",
    "ResponseParser",
    # Onboarding 数据模型
    "OnboardingProfileData",
    "OnboardingPersonalityData",
    # 核心数据模型
    "ClassificationResult",
    "DecisionReport",
    "DecisionType",
    "ExportFormat",
    "HistoryRecord",
    "MBTIType",
    "PersonalityAssessment",
    "PreferenceTag",
    "RecommendedOption",
    "ResearchResult",
    "SearchResult",
    "UserProfile",
]
