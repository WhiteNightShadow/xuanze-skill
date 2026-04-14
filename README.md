# 选择.Skill (xuanze-skill)

> 被动式智能决策辅助 Skill 模块 — 由宿主 LLM Agent 加载和编排

选择.Skill 是一个遵循 Skill-as-Module 架构的 Python 模块，由宿主 Agent（如 Claude）通过 Python API 调用。Skill 专注于数据管理、Prompt 构建和响应解析，分类、联网搜索和 LLM 推理均由宿主 Agent 自身完成。

## ✨ 功能特色

- **Skill-as-Module 架构**：作为被动模块被宿主 Agent 加载，无 CLI、无内置 LLM 调用
- **个性化推荐**：基于用户画像（MBTI、偏好标签、历史决策）组装分析指引 Prompt
- **结构化报告**：Top 3 推荐选项、优劣势对比、风险提示、个性化建议
- **偏好学习**：通过累积评分算法逐步建立偏好画像，越用越懂你
- **多种可视化**（可选）：文本时间线、饼图、折线图、词云
- **灵活导出**（可选）：支持 Markdown、PDF、PNG 格式

## ⚡ 快速开始（一键配置）

在你的 AI 编码工具（Cursor / Claude Code / Kiro / Codex 等）的对话框中直接输入：

```
请帮我配置skill并在后续触发选择相关操作的时候查阅该skill：https://github.com/WhiteNightShadow/xuanze-skill
```
初次加载需要用户输入信息建档，后续进行个性化分析

AI 会自动完成下载、配置，并在后续决策相关任务中自动调用该 Skill。

> 💡 支持所有能读取 GitHub 仓库的 AI 编码工具，包括但不限于：
> - **Cursor** — 在 Chat / Composer 中粘贴上述指令
> - **Claude Code** — 在终端对话中直接输入
> - **Kiro** — 在聊天框中输入即可
> - **Codex / GPT** — 在对话框中输入，配合代码解释器使用

### 配置后会发生什么？

1. **首次使用**：AI 会引导你完成建档（MBTI 人格测试、基础信息采集等，均可选择跳过）
2. **后续使用**：当你在对话中说出"帮我选"、"推荐一下"、"纠结中"等决策相关的话时，AI 会自动调用该 Skill，基于你的画像和历史偏好进行个性化分析
3. **越用越懂你**：每次决策后自动更新偏好标签，推荐会越来越贴合你的口味

## 📦 安装

### 环境要求

- Python 3.10+

### 安装核心依赖

```bash
pip install -r requirements.txt
```

或使用 `pyproject.toml`：

```bash
pip install .
```

安装可选的可视化/导出依赖：

```bash
pip install ".[viz]"
```

安装开发依赖：

```bash
pip install ".[dev]"
```

## 🚀 API 使用指南

### 基本用法

```python
from xuanze_core import XuanzeSkill

skill = XuanzeSkill()
```

### 1. 初始化（首次使用）

```python
skill.initialize()
```

### 2. Onboarding：保存用户画像

```python
# 保存基础信息
skill.save_profile({
    "age": 25,
    "city": "北京",
    "occupation": "软件工程师",
    "hobbies": ["编程", "阅读"],
})

# 保存人格信息
skill.save_personality({
    "mbti_type": "INTJ",
    "zodiac_sign": "天蝎座",
})

# 或使用内置 MBTI 测试
questions = skill.get_quiz_questions()
# Agent 在对话中逐题提问，收集答案后：
mbti_result = skill.calculate_mbti({0: "I", 1: "N", 2: "T", 3: "J", ...})
skill.save_personality({"mbti_type": mbti_result})
```

### 3. 决策流程

```python
# 构建分析指引 Prompt（自动加载画像、偏好、历史）
prompt = skill.build_decision_prompt(
    question="考研还是工作？",
    decision_type="long_term",
    research_summary="根据2024年数据，计算机硕士就业率95%...",
)

# Agent 基于 prompt 生成决策分析（JSON 格式）
# agent_analysis = agent.generate(prompt)

# 解析为结构化报告
report = skill.parse_decision_response(
    response='{"question_summary": "考研还是工作", ...}',
    decision_type="long_term",
)

# 后处理：更新偏好评分 + 归档历史
skill.finalize_decision(report)
```

### 4. 查询数据

```python
# 查询历史记录
history = skill.get_history(decision_type="long_term", limit=5)

# 获取偏好标签
tags = skill.get_preference_tags()

# 获取用户画像
profile = skill.get_profile()

# 获取相关历史
related = skill.get_related_history("考研还是工作？")
```

## 🏗️ 项目结构

```
xuanze-skill/
├── SKILL.md                  # Agent 编排指令文档
├── README.md                 # 项目说明文档
├── pyproject.toml            # 项目元数据与构建配置
├── requirements.txt          # Python 依赖列表
├── xuanze_core/             # 核心代码包
│   ├── __init__.py           # 包导出
│   ├── skill_api.py          # XuanzeSkill 统一 API 入口
│   ├── models.py             # Pydantic 数据模型
│   ├── onboarding.py         # 首次引导模块（纯数据 API）
│   ├── profile_manager.py    # 用户画像管理
│   ├── decision_engine.py    # PromptBuilder + ResponseParser
│   ├── preference_scorer.py  # 偏好评分算法
│   ├── history.py            # 历史记录管理
│   ├── visualizer.py         # 可视化模块（可选）
│   └── exporter.py           # 导出模块（可选）
├── prompts/                  # Prompt 模板
│   ├── long_term.txt
│   ├── short_term.txt
│   └── mbti_quiz.json
├── examples/                 # 示例文件
│   ├── example_college.md
│   └── example_lunch.md
└── tests/                    # 测试文件
```

## 🛠️ 技术栈

| 领域 | 技术方案 |
|------|---------|
| 数据校验 | Pydantic v2 |
| 可视化（可选） | rich + matplotlib + wordcloud |
| PDF 导出（可选） | fpdf2 |
| 历史存储 | JSONL 文件 |

## 📄 许可证

MIT License
