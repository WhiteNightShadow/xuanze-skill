# 选择.Skill — 用户画像管理器
"""
Profile_Manager 负责读写 profile.json 和 personality.json，
使用 Pydantic 模型校验所有数据，处理 JSON 损坏场景。

Requirements: R4.3, R5.1, R5.2, R5.3, R5.4
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from xuanze_core.models import PersonalityAssessment, UserProfile

logger = logging.getLogger(__name__)

# 默认缓存目录
DEFAULT_CACHE_DIR = ".xuanze_cache"

# 文件名常量
PROFILE_FILENAME = "profile.json"
PERSONALITY_FILENAME = "personality.json"


class ProfileError(Exception):
    """画像操作异常基类"""


class CorruptedFileError(ProfileError):
    """文件损坏异常，包含文件名以便提示用户重置"""

    def __init__(self, filename: str, detail: str) -> None:
        self.filename = filename
        self.detail = detail
        super().__init__(
            f"文件 {filename} 已损坏: {detail}。"
            f"可调用 reset_file('{filename}') 重置为默认空状态。"
        )


class ProfileManager:
    """用户画像管理器

    管理 profile.json 和 personality.json 的读写操作，
    所有数据通过 Pydantic 模型校验。

    Args:
        cache_dir: 缓存目录路径，默认为 .xuanze_cache
    """

    def __init__(self, cache_dir: str = DEFAULT_CACHE_DIR) -> None:
        self.cache_dir = Path(cache_dir)

    # ── profile.json 读写 ─────────────────────────────────

    def load_profile(self) -> UserProfile:
        """读取 profile.json 并返回 UserProfile 实例。

        Returns:
            UserProfile: 校验后的用户画像对象

        Raises:
            CorruptedFileError: JSON 解析失败或 Pydantic 校验失败时抛出
            FileNotFoundError: 文件不存在时抛出
        """
        filepath = self.cache_dir / PROFILE_FILENAME
        if not filepath.exists():
            raise FileNotFoundError(f"文件不存在: {filepath}")

        raw = filepath.read_text(encoding="utf-8")

        # 解析 JSON
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CorruptedFileError(PROFILE_FILENAME, f"JSON 解析失败: {exc}") from exc

        # Pydantic 校验
        try:
            return UserProfile.model_validate(data)
        except ValidationError as exc:
            raise CorruptedFileError(PROFILE_FILENAME, f"数据校验失败: {exc}") from exc

    def save_profile(self, profile: UserProfile) -> None:
        """将 UserProfile 写入 profile.json。

        写入前自动更新 updated_at 时间戳。

        Args:
            profile: 要保存的用户画像对象
        """
        filepath = self.cache_dir / PROFILE_FILENAME
        # 更新时间戳
        profile.updated_at = datetime.now()
        filepath.write_text(
            profile.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def update_profile(self, updates: dict[str, Any]) -> UserProfile:
        """合并更新字段并保存。

        读取现有画像，将 updates 中的字段合并到现有数据上，
        然后校验并保存。

        Args:
            updates: 要更新的字段字典

        Returns:
            UserProfile: 更新后的用户画像对象
        """
        # 加载现有画像
        profile = self.load_profile()
        # 合并更新：将现有数据 dump 为 dict，覆盖更新字段
        current_data = profile.model_dump()
        current_data.update(updates)
        # 重新校验
        updated_profile = UserProfile.model_validate(current_data)
        self.save_profile(updated_profile)
        return updated_profile

    # ── personality.json 读写 ─────────────────────────────

    def load_personality(self) -> PersonalityAssessment:
        """读取 personality.json 并返回 PersonalityAssessment 实例。

        Returns:
            PersonalityAssessment: 校验后的人格评估对象

        Raises:
            CorruptedFileError: JSON 解析失败或 Pydantic 校验失败时抛出
            FileNotFoundError: 文件不存在时抛出
        """
        filepath = self.cache_dir / PERSONALITY_FILENAME
        if not filepath.exists():
            raise FileNotFoundError(f"文件不存在: {filepath}")

        raw = filepath.read_text(encoding="utf-8")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CorruptedFileError(PERSONALITY_FILENAME, f"JSON 解析失败: {exc}") from exc

        try:
            return PersonalityAssessment.model_validate(data)
        except ValidationError as exc:
            raise CorruptedFileError(PERSONALITY_FILENAME, f"数据校验失败: {exc}") from exc

    def save_personality(self, personality: PersonalityAssessment) -> None:
        """将 PersonalityAssessment 写入 personality.json。

        Args:
            personality: 要保存的人格评估对象
        """
        filepath = self.cache_dir / PERSONALITY_FILENAME
        filepath.write_text(
            personality.model_dump_json(indent=2),
            encoding="utf-8",
        )

    # ── 文件重置 ──────────────────────────────────────────

    def reset_file(self, filename: str) -> None:
        """重置损坏的文件为默认空状态。

        支持重置 profile.json 和 personality.json。

        Args:
            filename: 要重置的文件名（profile.json 或 personality.json）

        Raises:
            ValueError: 不支持的文件名
        """
        filepath = self.cache_dir / filename

        if filename == PROFILE_FILENAME:
            # 重置为空的 UserProfile
            default = UserProfile()
            filepath.write_text(
                default.model_dump_json(indent=2),
                encoding="utf-8",
            )
            logger.info("已重置 %s 为默认空状态", filename)

        elif filename == PERSONALITY_FILENAME:
            # 重置为空的 PersonalityAssessment
            default = PersonalityAssessment()
            filepath.write_text(
                default.model_dump_json(indent=2),
                encoding="utf-8",
            )
            logger.info("已重置 %s 为默认空状态", filename)

        else:
            raise ValueError(
                f"不支持重置文件 '{filename}'，"
                f"仅支持 '{PROFILE_FILENAME}' 和 '{PERSONALITY_FILENAME}'"
            )
