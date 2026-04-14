# 选择.Skill — Agent 编排指令文档

## 1. Skill 名称和描述

**选择.Skill**（xuanze-skill）是一个被动式智能决策辅助 Skill 模块。

你（宿主 Agent）负责所有用户交互、问题分类、联网搜索和 LLM 推理。本 Skill 为你提供：
- 用户画像管理（基础信息 + 人格评估 + 偏好标签）
- Prompt 模板加载与组装（将画像、偏好、历史、搜索结果注入分析指引）
- 响应解析（将你的 JSON 输出解析为结构化 DecisionReport）
- 偏好评分与历史归档（每次决策后自动更新）

典型场景：
- **长期选择**：志愿填报、城市选择、职业规划、买房决策、结婚对象
- **短期选择**：午餐推荐、周末活动、电影挑选、购物选择、礼物推荐

---

## 2. 触发条件

当用户消息中包含以下短语或语义时，激活本 Skill 的决策工作流：

| 触发短语 | 示例 |
|---------|------|
| `帮我选` | "帮我选一个适合的笔记本电脑" |
| `该选哪个` | "该选哪个城市定居？" |
| `xx 还是 xx` | "考研还是工作？" |
| `推荐一下` | "推荐一下周末去哪玩" |
| `选择困难` | "选择困难，不知道中午吃什么" |

也包括语义等价的表达，如"帮我决定"、"不知道选什么"、"纠结中"等。

---

## 3. Python 环境准备

```python
from xuanze_core.skill_api import XuanzeSkill

skill = XuanzeSkill()
skill.initialize()  # 首次使用时创建 .xuanze_cache/ 目录结构
```

`initialize()` 会创建以下缓存文件（已存在则跳过）：
- `.xuanze_cache/profile.json` — 用户画像（含偏好标签）
- `.xuanze_cache/personality.json` — 人格评估
- `.xuanze_cache/history/long_term.jsonl` — 长期决策历史
- `.xuanze_cache/history/short_term.jsonl` — 短期决策历史

---

## 4. Onboarding 流程（首次使用引导）

### 4.1 检查是否需要 Onboarding

检查 `.xuanze_cache/` 目录是否存在。如果不存在，执行以下引导流程。

### 4.2 人格评估

在对话中询问用户希望如何建立人格画像，提供三个选项：

**选项 A：内置测试（推荐）**

```python
# 获取 MBTI 测试题
questions = skill.get_quiz_questions()

# 在对话中逐题向用户提问
# 每题包含 text（题目文本）和 options（选项列表）
# 每个 option 包含 label、text、direction 字段
# 收集用户选择，记录每题的 direction 值

answers = {}  # {题目索引: direction字母}
for i, q in enumerate(questions):
    # 向用户展示 q["text"] 和 q["options"]
    # 用户选择后，记录对应 option 的 direction
    answers[i] = user_selected_direction  # 如 "E", "I", "S", "N" 等

# 计算 MBTI 类型
mbti_result = skill.calculate_mbti(answers)  # 返回如 "INTJ"

# 保存人格数据
skill.save_personality({"mbti_type": mbti_result})
```

**选项 B：自定义输入**

在对话中询问用户的 MBTI 类型、星座、生肖等信息（所有字段均可选）：

```python
skill.save_personality({
    "mbti_type": "INTJ",        # 可选，必须是 16 种标准 MBTI 类型之一
    "zodiac_sign": "天蝎座",     # 可选
    "chinese_zodiac": "龙",      # 可选
    "blood_type": "A",           # 可选
    "personality_tags": ["内向", "理性"],  # 可选，自由标签
})
```

**选项 C：跳过**

用户可以跳过人格评估，后续决策将基于基础信息和客观数据。

### 4.3 基础信息采集

在对话中询问用户的基础信息（所有字段均可选，用户可跳过任意字段）：

```python
skill.save_profile({
    "age": 25,                              # 可选，1-150
    "gender": "男",                          # 可选
    "height": 175.0,                         # 可选，cm
    "weight": 70.0,                          # 可选，kg
    "city": "北京",                           # 可选
    "occupation": "软件工程师",                # 可选
    "health_conditions": ["近视"],            # 可选
    "hobbies": ["编程", "阅读", "跑步"],      # 可选
    "value_orientation": "追求成长与平衡",     # 可选
    "custom_fields": {"学历": "本科"},        # 可选，任意键值对
})
```

`save_profile` 支持增量更新：只提交用户实际回答的字段，已有数据不会被覆盖。

---

## 5. 分类指引

收到用户的决策问题后，你需要自行判断属于哪种决策类型：

### 长期选择（`long_term`）

影响深远、需要综合多维度信息的重大决策：
- 志愿填报、专业选择
- 城市选择、定居地点
- 职业规划、跳槽转行
- 买房、买车
- 结婚、重大人生规划
- 投资理财方向

**特征**：影响时间跨度长、涉及多个维度（经济、发展、个人适配）、决策成本高、难以逆转。

### 短期选择（`short_term`）

即时性强、偏好驱动的日常决策：
- 午餐、晚餐推荐
- 周末活动安排
- 电影、书籍挑选
- 购物选择（日用品、服装）
- 礼物推荐
- 旅行目的地（短途）

**特征**：影响时间跨度短、偏好驱动、决策成本低、容易调整。

### 判断规则

1. 如果问题涉及人生方向、大额支出、长期承诺 → `long_term`
2. 如果问题涉及日常消费、即时体验、短期安排 → `short_term`
3. 如果不确定，倾向于 `long_term`（更全面的分析不会有害）

---

## 6. 搜索指引

### 长期选择：始终搜索

长期决策需要充分的信息支撑。使用你的 MCP 搜索工具进行联网搜索，收集：
- 行业数据、就业前景、薪资水平
- 城市生活成本、发展规划
- 专业排名、学校评价
- 市场行情、政策变化
- 用户评价、经验分享

将搜索结果整理为文本摘要，作为 `research_summary` 传入。

### 短期选择：按需搜索

短期决策通常不需要搜索，但以下情况建议搜索：
- **位置相关**：附近餐厅、本地活动（需要实时信息）
- **时间敏感**：电影上映时间、活动日期、天气情况
- **价格比较**：商品价格、优惠信息
- **评价参考**：餐厅评分、产品口碑

如果不需要搜索，`research_summary` 传空字符串即可。

---

## 7. 决策分析工作流

收到用户的决策问题后，按以下步骤执行：

### Step 1：初始化

```python
from xuanze_core.skill_api import XuanzeSkill

skill = XuanzeSkill()
skill.initialize()
```

### Step 2：分类问题

根据第 5 节的分类指引，判断 `decision_type`：`"long_term"` 或 `"short_term"`。

### Step 3：联网搜索（按需）

根据第 6 节的搜索指引，使用 MCP 搜索工具收集信息，整理为 `research_summary` 文本。

### Step 4：构建分析 Prompt

```python
prompt = skill.build_decision_prompt(
    question="用户的原始问题文本",
    decision_type="long_term",  # 或 "short_term"
    research_summary="搜索结果摘要文本",  # 无搜索时传空字符串
)
```

此方法会自动：
- 加载对应类型的 Prompt 模板
- 注入用户画像和人格评估数据
- 注入偏好标签（已确立的偏好）
- 注入相关历史决策摘要
- 注入搜索结果
- 缺失数据时优雅降级（不会报错）

### Step 5：生成决策分析

基于返回的 `prompt` 指引，生成决策分析。**你必须严格按照第 8 节的 JSON 格式输出。**

### Step 6：解析响应

```python
report = skill.parse_decision_response(
    response=your_json_output,  # 你在 Step 5 生成的 JSON 文本
    decision_type="long_term",  # 与 Step 4 一致
)
```

### Step 7：后处理（偏好更新 + 历史归档）

```python
skill.finalize_decision(report)
```

此方法会自动：
- 分析决策内容，提取偏好标签并更新累积评分
- 将决策记录追加到对应的历史文件

### 完整代码示例

```python
from xuanze_core.skill_api import XuanzeSkill

skill = XuanzeSkill()
skill.initialize()

# 构建 prompt
prompt = skill.build_decision_prompt(
    question="考研还是工作？",
    decision_type="long_term",
    research_summary="根据2024年数据，计算机硕士就业率95%，平均起薪15k...",
)

# 你基于 prompt 生成 JSON 格式的决策分析（见第 8 节）
agent_json_output = "..."  # 你的 JSON 输出

# 解析为结构化报告
report = skill.parse_decision_response(agent_json_output, "long_term")

# 后处理
skill.finalize_decision(report)
```

---

## 8. 输出 JSON 格式

你在 Step 5 中生成的决策分析必须严格遵循以下 JSON 结构：

```json
{
  "question_summary": "用一句话概括用户的决策问题",
  "recommended_options": [
    {
      "name": "选项名称",
      "reasoning": "推荐理由（结合用户画像、偏好标签和客观数据）",
      "pros": ["优势1", "优势2", "优势3"],
      "cons": ["劣势1", "劣势2"],
      "risk_warnings": ["风险提示1"],
      "score": 8.5
    },
    {
      "name": "选项名称2",
      "reasoning": "推荐理由",
      "pros": ["优势1", "优势2"],
      "cons": ["劣势1"],
      "risk_warnings": ["风险提示1"],
      "score": 7.2
    },
    {
      "name": "选项名称3",
      "reasoning": "推荐理由",
      "pros": ["优势1"],
      "cons": ["劣势1", "劣势2"],
      "risk_warnings": [],
      "score": 6.0
    }
  ],
  "personalized_suggestions": "基于用户画像和偏好标签的个性化建议",
  "source_references": ["信息来源1", "信息来源2"]
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `question_summary` | string | ✅ | 一句话概括用户的决策问题 |
| `recommended_options` | array | ✅ | 推荐选项列表，最多 3 个，按 score 降序 |
| `recommended_options[].name` | string | ✅ | 选项名称 |
| `recommended_options[].reasoning` | string | ✅ | 推荐理由 |
| `recommended_options[].pros` | string[] | ✅ | 优势列表 |
| `recommended_options[].cons` | string[] | ✅ | 劣势列表 |
| `recommended_options[].risk_warnings` | string[] | ❌ | 风险提示（长期决策必填） |
| `recommended_options[].score` | float | ❌ | 综合评分 1.0-10.0 |
| `personalized_suggestions` | string | ✅ | 个性化建议，引用用户画像和偏好 |
| `source_references` | string[] | ❌ | 信息来源列表，无搜索时为空列表 |

### 输出规则

1. `recommended_options` 最多 3 个（超过 3 个会被截断为前 3 个）
2. 长期决策的每个选项至少包含 1 条 `risk_warnings`
3. `personalized_suggestions` 应引用用户的具体偏好标签或画像信息
4. 仅输出 JSON，不要包含额外文字（支持 markdown 代码块包裹）

---

## 9. 报告展示指引

解析完成后，将 `DecisionReport` 格式化展示给用户。建议格式：

### 展示结构

```
📊 决策报告
分类：长期选择 / 短期选择

🥇 推荐 1：{name}（评分：{score}）
   💡 理由：{reasoning}
   ✅ 优势：{pros 逐条列出}
   ⚠️ 劣势：{cons 逐条列出}
   🚨 风险：{risk_warnings 逐条列出}（如有）

🥈 推荐 2：{name}（评分：{score}）
   ...

🥉 推荐 3：{name}（评分：{score}）
   ...

💡 个性化建议：
{personalized_suggestions}

📚 信息来源：
{source_references 逐条列出}（如有）
```

### 展示要点

- Top 3 推荐选项按评分从高到低排列
- 每个选项展示优劣势对比表
- 长期决策突出风险提示
- 个性化建议放在最后，语气亲切
- 如有信息来源，附在报告末尾

---

## 10. 偏好更新说明

`finalize_decision(report)` 会自动完成以下操作，无需你额外处理：

1. **偏好标签提取**：从决策报告中分析关键词，提取偏好标签候选（如"注重性价比"、"重视健康"、"追求体验"等）
2. **累积评分更新**：每个标签的评分变化限制在 [-1.0, +1.0] 之间，防止单次决策主导偏好画像
3. **时间衰减**：旧决策的影响会随时间衰减，近期选择权重更高
4. **阈值判断**：评分达到 5.0 以上的标签被视为"已确立偏好"，会在后续 Prompt 中体现
5. **历史归档**：决策记录追加到对应的 JSONL 历史文件

---

## 附录：数据查询 API

以下方法可用于查询用户数据，在对话中按需使用：

```python
# 获取用户画像（含人格评估）
profile = skill.get_profile()
# 返回 {"profile": {...}, "personality": {...}}

# 查询历史记录
history = skill.get_history(decision_type="long_term", limit=10)
# 返回历史记录字典列表

# 获取与当前问题相关的历史记录
related = skill.get_related_history("考研还是工作？", limit=5)
# 返回相关历史记录字典列表

# 获取偏好标签
tags = skill.get_preference_tags()
# 返回 [{"name": "注重性价比", "score": 6.5, "decision_count": 5, ...}, ...]
```
