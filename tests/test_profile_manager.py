# Profile_Manager 单元测试
"""
测试 ProfileManager 的读写、更新、重置和损坏文件处理逻辑。
Requirements: R4.3, R5.1, R5.2, R5.3, R5.4
"""

from __future__ import annotations

import json

import pytest

from xuanze_core.models import (
    MBTIType,
    PersonalityAssessment,
    PreferenceTag,
    UserProfile,
)
from xuanze_core.profile_manager import (
    CorruptedFileError,
    PERSONALITY_FILENAME,
    PROFILE_FILENAME,
    ProfileManager,
)


@pytest.fixture
def cache_dir(tmp_path):
    """创建临时缓存目录并返回 ProfileManager 实例"""
    return tmp_path


@pytest.fixture
def pm(cache_dir):
    """创建 ProfileManager 实例"""
    return ProfileManager(cache_dir=str(cache_dir))


# ── profile.json 读写 ────────────────────────────────────


class TestLoadSaveProfile:
    """测试 profile.json 的读写 round-trip"""

    def test_save_and_load_default_profile(self, pm, cache_dir):
        """保存默认画像后能正确读回"""
        profile = UserProfile()
        pm.save_profile(profile)
        loaded = pm.load_profile()
        assert loaded.age is None
        assert loaded.preference_tags == []
        assert loaded.custom_fields == {}

    def test_save_and_load_profile_with_data(self, pm, cache_dir):
        """保存含数据的画像后能正确读回"""
        tag = PreferenceTag(name="注重性价比", score=3.5, decision_count=2)
        profile = UserProfile(
            age=25,
            gender="男",
            city="北京",
            occupation="工程师",
            hobbies=["编程", "阅读"],
            custom_fields={"学历": "本科"},
            preference_tags=[tag],
        )
        pm.save_profile(profile)
        loaded = pm.load_profile()
        assert loaded.age == 25
        assert loaded.gender == "男"
        assert loaded.city == "北京"
        assert len(loaded.preference_tags) == 1
        assert loaded.preference_tags[0].name == "注重性价比"
        assert loaded.custom_fields["学历"] == "本科"

    def test_load_profile_file_not_found(self, pm):
        """文件不存在时抛出 FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            pm.load_profile()

    def test_save_profile_updates_timestamp(self, pm, cache_dir):
        """保存时 updated_at 被更新"""
        profile = UserProfile()
        old_time = profile.updated_at
        pm.save_profile(profile)
        loaded = pm.load_profile()
        # updated_at 应该被刷新（至少不早于 old_time）
        assert loaded.updated_at >= old_time


# ── update_profile ────────────────────────────────────────


class TestUpdateProfile:
    """测试合并更新字段"""

    def test_update_single_field(self, pm, cache_dir):
        """更新单个字段，其他字段保持不变"""
        pm.save_profile(UserProfile(age=20, city="上海"))
        updated = pm.update_profile({"city": "深圳"})
        assert updated.age == 20
        assert updated.city == "深圳"

    def test_update_custom_fields(self, pm, cache_dir):
        """更新 custom_fields"""
        pm.save_profile(UserProfile(custom_fields={"学历": "本科"}))
        updated = pm.update_profile({"custom_fields": {"学历": "硕士", "专业": "CS"}})
        assert updated.custom_fields == {"学历": "硕士", "专业": "CS"}

    def test_update_with_invalid_age_raises(self, pm, cache_dir):
        """更新时 Pydantic 校验仍然生效"""
        pm.save_profile(UserProfile(age=25))
        with pytest.raises(Exception):
            pm.update_profile({"age": 200})


# ── personality.json 读写 ─────────────────────────────────


class TestLoadSavePersonality:
    """测试 personality.json 的读写"""

    def test_save_and_load_default_personality(self, pm, cache_dir):
        """保存默认人格评估后能正确读回"""
        personality = PersonalityAssessment()
        pm.save_personality(personality)
        loaded = pm.load_personality()
        assert loaded.mbti_type is None
        assert loaded.assessment_method == "none"

    def test_save_and_load_personality_with_data(self, pm, cache_dir):
        """保存含数据的人格评估后能正确读回"""
        personality = PersonalityAssessment(
            mbti_type=MBTIType.INFJ,
            zodiac_sign="天蝎座",
            chinese_zodiac="龙",
            blood_type="A",
            personality_tags=["内向", "直觉"],
            assessment_method="custom_input",
        )
        pm.save_personality(personality)
        loaded = pm.load_personality()
        assert loaded.mbti_type == MBTIType.INFJ
        assert loaded.zodiac_sign == "天蝎座"
        assert loaded.personality_tags == ["内向", "直觉"]

    def test_load_personality_file_not_found(self, pm):
        """文件不存在时抛出 FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            pm.load_personality()


# ── JSON 损坏处理 ─────────────────────────────────────────


class TestCorruptedFileHandling:
    """测试 JSON 损坏场景的错误处理"""

    def test_corrupted_profile_json(self, pm, cache_dir):
        """profile.json 包含无效 JSON 时抛出 CorruptedFileError"""
        filepath = cache_dir / PROFILE_FILENAME
        filepath.write_text("{invalid json!!!", encoding="utf-8")
        with pytest.raises(CorruptedFileError) as exc_info:
            pm.load_profile()
        assert PROFILE_FILENAME in str(exc_info.value)
        assert "reset_file" in str(exc_info.value)

    def test_corrupted_personality_json(self, pm, cache_dir):
        """personality.json 包含无效 JSON 时抛出 CorruptedFileError"""
        filepath = cache_dir / PERSONALITY_FILENAME
        filepath.write_text("not json at all", encoding="utf-8")
        with pytest.raises(CorruptedFileError) as exc_info:
            pm.load_personality()
        assert PERSONALITY_FILENAME in str(exc_info.value)

    def test_invalid_data_profile(self, pm, cache_dir):
        """profile.json 包含合法 JSON 但不符合 Pydantic 模型时抛出 CorruptedFileError"""
        filepath = cache_dir / PROFILE_FILENAME
        # age 超出范围
        filepath.write_text(json.dumps({"age": -5}), encoding="utf-8")
        with pytest.raises(CorruptedFileError):
            pm.load_profile()

    def test_invalid_data_personality(self, pm, cache_dir):
        """personality.json 包含非法 MBTI 类型时抛出 CorruptedFileError"""
        filepath = cache_dir / PERSONALITY_FILENAME
        filepath.write_text(json.dumps({"mbti_type": "XXXX"}), encoding="utf-8")
        with pytest.raises(CorruptedFileError):
            pm.load_personality()


# ── reset_file ────────────────────────────────────────────


class TestResetFile:
    """测试文件重置功能"""

    def test_reset_profile(self, pm, cache_dir):
        """重置 profile.json 后能正常读取为默认空状态"""
        # 先写入损坏数据
        filepath = cache_dir / PROFILE_FILENAME
        filepath.write_text("corrupted!", encoding="utf-8")
        # 重置
        pm.reset_file(PROFILE_FILENAME)
        # 验证可以正常读取
        profile = pm.load_profile()
        assert profile.age is None
        assert profile.preference_tags == []

    def test_reset_personality(self, pm, cache_dir):
        """重置 personality.json 后能正常读取为默认空状态"""
        filepath = cache_dir / PERSONALITY_FILENAME
        filepath.write_text("corrupted!", encoding="utf-8")
        pm.reset_file(PERSONALITY_FILENAME)
        personality = pm.load_personality()
        assert personality.mbti_type is None
        assert personality.assessment_method == "none"

    def test_reset_unsupported_file_raises(self, pm):
        """重置不支持的文件名时抛出 ValueError"""
        with pytest.raises(ValueError, match="不支持重置文件"):
            pm.reset_file("unknown.json")
