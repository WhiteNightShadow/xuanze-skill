# 选择.Skill — 历史记录管理器
"""
History_Manager 负责决策记录的存储、查询和筛选。

历史记录以 JSONL 格式存储在 .xuanze_cache/history/ 目录下，
按决策类型分为 long_term.jsonl 和 short_term.jsonl 两个文件。
每行一个 HistoryRecord JSON 对象，支持 append-only 写入。

Requirements: R12.1, R12.2, R12.3, R12.4, R12.5
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from xuanze_core.models import DecisionType, HistoryRecord

logger = logging.getLogger(__name__)

# 默认缓存目录
DEFAULT_CACHE_DIR = ".xuanze_cache"

# JSONL 文件名映射
HISTORY_FILES: dict[DecisionType, str] = {
    DecisionType.LONG_TERM: "history/long_term.jsonl",
    DecisionType.SHORT_TERM: "history/short_term.jsonl",
}


class HistoryManager:
    """历史记录管理器

    管理决策记录的追加写入、条件查询和相关历史检索。
    自动处理 JSONL 文件中的损坏行（跳过并记录警告）。

    Args:
        cache_dir: 缓存目录路径，默认为 .xuanze_cache
    """

    def __init__(self, cache_dir: str = DEFAULT_CACHE_DIR) -> None:
        self.cache_dir = Path(cache_dir)

    def _get_history_path(self, decision_type: DecisionType) -> Path:
        """获取对应决策类型的 JSONL 文件路径。

        Args:
            decision_type: 决策类型（长期/短期）

        Returns:
            JSONL 文件的 Path 对象
        """
        return self.cache_dir / HISTORY_FILES[decision_type]

    def append_record(self, record: HistoryRecord) -> None:
        """追加 HistoryRecord 到对应 JSONL 文件。

        根据记录的 classification 字段决定写入 long_term.jsonl
        或 short_term.jsonl。每条记录序列化为单行 JSON 后追加。

        Args:
            record: 要追加的历史记录对象
        """
        filepath = self._get_history_path(record.classification)

        # 确保目录存在
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # 序列化为单行 JSON 并追加
        json_line = record.model_dump_json()
        with filepath.open("a", encoding="utf-8") as f:
            f.write(json_line + "\n")

        logger.info(
            "已追加历史记录到 %s（问题: %s）",
            filepath.name,
            record.report.question_summary[:30],
        )

    def _load_records_from_file(self, filepath: Path) -> list[HistoryRecord]:
        """从单个 JSONL 文件加载所有有效记录。

        损坏行（JSON 解析失败或 Pydantic 校验失败）会被跳过，
        并记录警告日志，继续处理后续有效记录。

        Args:
            filepath: JSONL 文件路径

        Returns:
            有效的 HistoryRecord 列表
        """
        if not filepath.exists():
            return []

        records: list[HistoryRecord] = []
        skipped = 0

        with filepath.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                stripped = line.strip()
                if not stripped:
                    continue  # 跳过空行

                try:
                    record = HistoryRecord.model_validate_json(stripped)
                    records.append(record)
                except (ValidationError, ValueError) as exc:
                    skipped += 1
                    logger.warning(
                        "跳过 %s 第 %d 行（损坏）: %s",
                        filepath.name,
                        line_num,
                        exc,
                    )

        if skipped > 0:
            logger.warning(
                "%s 中共跳过 %d 行损坏记录", filepath.name, skipped
            )

        return records

    def query_records(
        self,
        decision_type: DecisionType | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        tags: list[str] | None = None,
    ) -> list[HistoryRecord]:
        """按条件查询历史记录。

        支持按决策类型、时间范围和标签筛选。所有条件为可选，
        未指定的条件不参与过滤。结果按时间戳升序排列。

        Args:
            decision_type: 决策类型过滤（None 表示查询所有类型）
            start_time: 起始时间（含），None 表示不限
            end_time: 结束时间（含），None 表示不限
            tags: 标签过滤列表，记录的 tags 或问题关键词匹配任一即返回

        Returns:
            符合条件的 HistoryRecord 列表，按时间戳升序排列
        """
        # 确定要读取的文件
        if decision_type is not None:
            files_to_read = [self._get_history_path(decision_type)]
        else:
            files_to_read = [
                self._get_history_path(dt) for dt in DecisionType
            ]

        # 加载所有记录
        all_records: list[HistoryRecord] = []
        for filepath in files_to_read:
            all_records.extend(self._load_records_from_file(filepath))

        # 应用时间范围过滤
        if start_time is not None:
            all_records = [r for r in all_records if r.timestamp >= start_time]
        if end_time is not None:
            all_records = [r for r in all_records if r.timestamp <= end_time]

        # 应用标签过滤：记录的 tags 或问题关键词匹配任一指定标签
        if tags:
            filtered: list[HistoryRecord] = []
            for record in all_records:
                # 检查记录标签是否与查询标签有交集
                record_tags_lower = {t.lower() for t in record.tags}
                query_tags_lower = {t.lower() for t in tags}
                if record_tags_lower & query_tags_lower:
                    filtered.append(record)
                    continue
                # 检查问题摘要是否包含查询标签关键词
                summary_lower = record.report.question_summary.lower()
                if any(tag.lower() in summary_lower for tag in tags):
                    filtered.append(record)
            all_records = filtered

        # 按时间戳升序排列
        all_records.sort(key=lambda r: r.timestamp)
        return all_records

    def get_related_history(
        self, question: str, limit: int = 5
    ) -> list[HistoryRecord]:
        """获取与当前问题相关的历史记录。

        通过简单的关键词匹配计算相关度：将问题分词后，
        统计每条历史记录中匹配的关键词数量，返回匹配度最高的记录。

        Args:
            question: 当前决策问题文本
            limit: 最多返回的记录数，默认 5

        Returns:
            相关度最高的 HistoryRecord 列表，按相关度降序排列
        """
        # 加载所有历史记录
        all_records: list[HistoryRecord] = []
        for dt in DecisionType:
            all_records.extend(
                self._load_records_from_file(self._get_history_path(dt))
            )

        if not all_records:
            return []

        # 提取问题中的关键词（简单分词：按空格和标点拆分，过滤短词）
        keywords = _extract_keywords(question)

        if not keywords:
            # 无有效关键词时按时间倒序返回最近记录
            all_records.sort(key=lambda r: r.timestamp, reverse=True)
            return all_records[:limit]

        # 计算每条记录的相关度得分
        scored: list[tuple[float, HistoryRecord]] = []
        for record in all_records:
            score = _compute_relevance(record, keywords)
            scored.append((score, record))

        # 按相关度降序排列，相关度相同时按时间倒序
        scored.sort(key=lambda x: (x[0], x[1].timestamp), reverse=True)

        # 返回 limit 条（仅包含有相关度的记录）
        return [record for _score, record in scored[:limit]]


def _extract_keywords(text: str) -> list[str]:
    """从文本中提取关键词。

    简单分词策略：按常见分隔符拆分，过滤长度 < 2 的词。
    适用于中文和英文混合文本。

    Args:
        text: 输入文本

    Returns:
        关键词列表（去除短词后的有效词列表）
    """
    import re

    # 按空格、中英文标点、特殊字符拆分
    separators = r'[\s,，。！？、；：\u201c\u201d\u2018\u2019（）()\[\]{}|/\\]+'
    tokens = re.split(separators, text)
    # 过滤长度不足 2 的短词（避免噪声）
    return [t for t in tokens if len(t) >= 2]


def _compute_relevance(record: HistoryRecord, keywords: list[str]) -> float:
    """计算单条记录与关键词列表的相关度得分。

    扫描记录的问题摘要、标签和推荐选项名称，
    统计匹配的关键词数量作为得分。得分越高表示越相关。

    Args:
        record: 历史记录
        keywords: 关键词列表

    Returns:
        相关度得分（匹配关键词数量，浮点数）
    """
    # 构建待匹配的文本
    text_parts = [
        record.report.question_summary,
        " ".join(record.tags),
    ]
    for option in record.report.recommended_options:
        text_parts.append(option.name)

    combined = " ".join(text_parts).lower()

    # 统计匹配数
    score = 0.0
    for kw in keywords:
        if kw.lower() in combined:
            score += 1.0

    return score
