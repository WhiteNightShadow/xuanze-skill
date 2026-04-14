# 选择.Skill — 偏好评分算法模块
"""
Preference_Scorer 负责在每次决策完成后分析决策内容，
提取偏好标签候选，更新累积评分，并应用时间衰减。

评分规则：
- 每次决策对单个标签的评分变化限制在 [-1.0, +1.0]
- 使用指数衰减模型（decay_factor^days_ago）降低旧决策权重
- 分数超过阈值（默认 5.0）的标签视为已确立偏好

Requirements: R21.1, R21.2, R21.3, R21.4, R21.5, R21.6
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from xuanze_core.models import DecisionReport, PreferenceTag

if TYPE_CHECKING:
    from xuanze_core.profile_manager import ProfileManager

logger = logging.getLogger(__name__)

# ── 预定义的偏好标签关键词映射 ──────────────────────────────
# 将决策报告中常见的关键词映射到偏好标签名称。
# 每个标签对应一组同义关键词，匹配任一即视为命中该标签。
TAG_KEYWORD_MAP: dict[str, list[str]] = {
    "注重性价比": ["性价比", "价格", "便宜", "实惠", "经济", "划算", "省钱", "成本"],
    "偏好稳定": ["稳定", "安全", "保守", "风险低", "可靠", "稳妥", "保障"],
    "追求体验": ["体验", "享受", "品质", "高端", "精致", "舒适", "氛围"],
    "重视健康": ["健康", "营养", "运动", "养生", "低脂", "有机", "绿色"],
    "注重效率": ["效率", "快速", "便捷", "省时", "高效", "方便"],
    "追求创新": ["创新", "新颖", "尝鲜", "潮流", "前沿", "新奇"],
    "重视社交": ["社交", "朋友", "聚会", "团队", "合作", "人脉"],
    "偏好自由": ["自由", "灵活", "自主", "独立", "弹性"],
    "注重成长": ["成长", "学习", "发展", "提升", "进步", "潜力"],
    "重视家庭": ["家庭", "家人", "亲情", "陪伴", "照顾"],
}


class PreferenceScorer:
    """选择偏好评分器

    通过分析决策报告内容提取偏好标签候选，并使用累积评分模型
    逐步建立用户偏好画像。支持时间衰减和阈值判断。

    Args:
        profile_manager: 用户画像管理器，用于读写 preference_tags
        threshold: 已确立偏好的分数阈值，默认 5.0
        decay_factor: 时间衰减因子，默认 0.95
    """

    THRESHOLD: float = 5.0
    MAX_SCORE_CHANGE: float = 1.0
    DECAY_FACTOR: float = 0.95

    def __init__(
        self,
        profile_manager: ProfileManager,
        threshold: float = 5.0,
        decay_factor: float = 0.95,
    ) -> None:
        self.profile_manager = profile_manager
        self.threshold = threshold
        self.decay_factor = decay_factor

    def extract_tags(self, report: DecisionReport) -> list[str]:
        """从决策报告中提取偏好标签候选。

        扫描报告的推荐选项（名称、推荐理由、优势、劣势）和
        个性化建议文本，匹配预定义关键词映射表中的标签。

        Args:
            report: 决策报告对象

        Returns:
            匹配到的偏好标签名称列表（去重）
        """
        # 收集所有待扫描的文本片段
        text_parts: list[str] = [
            report.question_summary,
            report.personalized_suggestions,
        ]
        for option in report.recommended_options:
            text_parts.append(option.name)
            text_parts.append(option.reasoning)
            text_parts.extend(option.pros)
            text_parts.extend(option.cons)

        combined_text = " ".join(text_parts)

        # 匹配关键词 → 标签
        matched_tags: list[str] = []
        for tag_name, keywords in TAG_KEYWORD_MAP.items():
            for keyword in keywords:
                if keyword in combined_text:
                    matched_tags.append(tag_name)
                    break  # 一个标签只需匹配一个关键词即可

        return matched_tags

    def clamp_score_change(self, delta: float) -> float:
        """将单次评分变化限制在 [-MAX_SCORE_CHANGE, +MAX_SCORE_CHANGE] 范围内。

        Args:
            delta: 原始评分变化量

        Returns:
            限制后的评分变化量
        """
        return max(-self.MAX_SCORE_CHANGE, min(self.MAX_SCORE_CHANGE, delta))

    def update_scores(
        self,
        report: DecisionReport,
        current_tags: list[PreferenceTag],
    ) -> list[PreferenceTag]:
        """根据新决策更新偏好标签评分。

        从报告中提取标签候选，对匹配到的标签增加评分（+1.0），
        对未匹配的现有标签不做变化。新标签自动创建。

        Args:
            report: 新生成的决策报告
            current_tags: 当前已有的偏好标签列表

        Returns:
            更新后的偏好标签列表
        """
        # 提取本次决策匹配的标签
        matched_tag_names = self.extract_tags(report)
        now = datetime.now()

        # 构建 name → PreferenceTag 索引
        tag_map: dict[str, PreferenceTag] = {tag.name: tag for tag in current_tags}

        for tag_name in matched_tag_names:
            if tag_name in tag_map:
                # 已有标签：增量更新评分
                existing = tag_map[tag_name]
                delta = self.clamp_score_change(1.0)
                tag_map[tag_name] = PreferenceTag(
                    name=existing.name,
                    score=existing.score + delta,
                    last_updated=now,
                    decision_count=existing.decision_count + 1,
                )
            else:
                # 新标签：初始评分为 clamped delta
                delta = self.clamp_score_change(1.0)
                tag_map[tag_name] = PreferenceTag(
                    name=tag_name,
                    score=delta,
                    last_updated=now,
                    decision_count=1,
                )

        return list(tag_map.values())

    def apply_decay(self, tags: list[PreferenceTag]) -> list[PreferenceTag]:
        """对所有标签应用时间衰减因子。

        衰减公式：score *= decay_factor ^ days_ago
        其中 days_ago 为标签上次更新距今的天数。

        Args:
            tags: 偏好标签列表

        Returns:
            应用衰减后的偏好标签列表（新列表，不修改原对象）
        """
        now = datetime.now()
        decayed_tags: list[PreferenceTag] = []

        for tag in tags:
            days_ago = (now - tag.last_updated).total_seconds() / 86400.0
            decay_multiplier = self.decay_factor ** days_ago
            decayed_score = tag.score * decay_multiplier

            decayed_tags.append(
                PreferenceTag(
                    name=tag.name,
                    score=decayed_score,
                    last_updated=tag.last_updated,
                    decision_count=tag.decision_count,
                )
            )

        return decayed_tags

    def get_established_preferences(
        self, tags: list[PreferenceTag]
    ) -> list[PreferenceTag]:
        """返回分数超过阈值的已确立偏好。

        Args:
            tags: 偏好标签列表

        Returns:
            分数 >= threshold 的标签列表
        """
        return [tag for tag in tags if tag.score >= self.threshold]

    def score_and_save(self, report: DecisionReport) -> list[PreferenceTag]:
        """完整评分流程：提取标签 → 更新评分 → 衰减 → 写入 profile.json。

        这是外部调用的主入口方法，编排完整的偏好评分更新流程。

        Args:
            report: 新生成的决策报告

        Returns:
            更新后的偏好标签列表
        """
        # 1. 加载当前画像中的偏好标签
        profile = self.profile_manager.load_profile()
        current_tags = profile.preference_tags

        # 2. 根据新决策更新评分
        updated_tags = self.update_scores(report, current_tags)

        # 3. 应用时间衰减
        decayed_tags = self.apply_decay(updated_tags)

        # 4. 写入 profile.json 的 preference_tags 字段
        profile.preference_tags = decayed_tags
        self.profile_manager.save_profile(profile)

        logger.info(
            "偏好评分更新完成，共 %d 个标签，其中 %d 个已确立",
            len(decayed_tags),
            len(self.get_established_preferences(decayed_tags)),
        )

        return decayed_tags
