# 短篇小说 NPC 角色卡系统

本目录只负责角色卡、公共剧情事件、知识边界和运行时 Prompt 编译，不包含 Harness、模型推理、训练、GGUF 转换或 Android 集成代码。

当前数据仅以 `../1453.txt` 至 `../1458.txt` 为事实来源。`../qa.json` 只用于测试问题和人工复核，不能覆盖原文证据。

## 已交付内容

```text
character_system/
├── schemas/
│   ├── npc_schema.json
│   └── story_event_schema.json
├── characters/
│   ├── lu_jiangxian.json
│   └── xuan_an.json
├── story/
│   └── story_events.jsonl
├── prompts/
│   ├── character_extraction.prompt
│   └── roleplay_system.prompt
├── runtime/
│   ├── knowledge_filter.py
│   ├── memory_retriever.py
│   ├── prompt_compiler.py
│   ├── retrieval.py
│   └── validation.py
├── scripts/
│   ├── compile_prompt.py
│   ├── generate_character_cards.py
│   ├── run_qa_cases.py
│   └── validate_character_data.py
├── tests/
│   ├── fixtures/scenarios.json
│   └── test_character_system.py
├── examples/
└── reports/
```

首批 NPC 为陆江仙和玄谙。两者使用完全相同的 `schema_version=1.0.0` 结构；公共剧情只保存在一份 JSONL 中。

## 设计说明

角色卡在基础结构上增加了以下字段：

- `schema_version`：为端侧数据迁移提供稳定版本。
- `aliases`：用于角色识别和检索，不改变主身份。
- `worldview_position`：供第一层全局摘要说明角色在世界中的位置。
- `core_motivations`、`behavior_rules`：分别保存稳定动机和可执行行为规律。
- `current_goal`：与静态动机分离，描述当前回合附近的目标。
- `evidence_refs`：以字段路径绑定原文证据，防止无证据人格堆叠。

公共事件增加了：

- `confidence`：事实整体可信度；低于确定阈值时 Prompt 会保留不确定措辞。
- `visibility`：事件允许进入哪些角色的候选知识。
- `keywords`：首版低依赖检索索引，可被 BM25 或向量检索替换。
- `knowledge_by_character`：记录每个角色的获知方式、获知时点和角色侧可信度。它能表达“事情早已发生，但该 NPC 后来才被告知”。

`story_cutoff` 使用稳定事件 ID。事件的 `time_index` 决定先后顺序，不能靠字符串大小比较。

## 一次生成调用的编译流程

```text
npc_id + 原始玩家输入 + RuntimeContext
        │
        ├─ 加载、校验角色卡
        ├─ 可替换检索器召回相关公共事件
        ├─ 时间、来源、可见性、角色白名单过滤
        ├─ 选择相关情节记忆和人物关系
        ├─ 按优先级放入字符预算
        └─ 输出 system + user 两条消息
                              │
                              └─ Harness 只调用一次生成模型
```

玩家原始输入只放入 `user` 消息，不会插值进可信的 System Prompt。编译调试信息保存在返回对象的 `debug`，也不会进入模型消息。

三层信息对应如下：

1. 全局摘要：身份、世界位置、主要背景、核心动机、剧情阶段。
2. 核心人格：价值观、8～12 个心理特征、表达规律、稳定行为和硬约束。
3. 情境切片：当前状态、相关关系、授权事实与个人经历。

## 直接运行

所有命令均从本目录执行：

```powershell
cd E:\DuanCe\novel_test\character_system
python scripts\validate_character_data.py
python -m unittest discover -s tests -v
```

编译单轮消息：

```powershell
python scripts\compile_prompt.py `
  --npc lu_jiangxian `
  --input "玄谙究竟是什么？" `
  --cutoff evt-010 `
  --max-chars 4500 `
  --debug
```

生成可检查示例：

```powershell
python scripts\compile_prompt.py `
  --npc lu_jiangxian `
  --input "玄谙究竟是什么？" `
  --cutoff evt-010 `
  --debug `
  --output examples\compiled_lu_jiangxian_evt010.json
```

把现有 `qa.json` 的问题编译成可直接送入模型的消息：

```powershell
python scripts\run_qa_cases.py `
  --npc xuan_an `
  --cutoff evt-018 `
  --output examples\qa_xuan_an_evt018.json
```

注意：`qa.json` 中的参考答案是全知式人工答案。运行时能否使用其中的信息，仍取决于指定 NPC 和截止点；脚本不会把参考答案注入模型消息。

## 可重复的角色卡生成流程

先生成带稳定行号的提取请求：

```powershell
python scripts\generate_character_cards.py prepare `
  --npc 陆江仙 玄谙 `
  --output build\extraction_request.txt
```

将请求交给任意支持严格 JSON 输出的离线或在线提取模型。模型结果不能直接发布，必须由人工核对后写入 `characters/` 和 `story/story_events.jsonl`，再运行：

```powershell
python scripts\validate_character_data.py
python scripts\generate_character_cards.py report `
  --output reports\character_cards.md
python -m unittest discover -s tests -v
```

这套流程验证：

- 字段类型、枚举、心理特征数量和数值范围；
- 事件 ID、时间序号和引用完整性；
- 原文文件、行号与范围是否存在；
- NPC、事件、关系和记忆的跨文件引用；
- 不同 NPC 是否使用同一字段结构。

仓库内的 Python 校验器是无第三方依赖的运行校验实现；`schemas/*.json` 是正式 JSON Schema 契约，可供 Harness 或带 JSON Schema 库的构建流程直接使用。

## Runtime API

```python
from pathlib import Path
from runtime import PromptCompiler, RuntimeContext

compiler = PromptCompiler(Path("E:/DuanCe/novel_test/character_system"))
compiled = compiler.build_npc_prompt(
    npc_id="lu_jiangxian",
    user_input="玄谙究竟是什么？",
    runtime_context=RuntimeContext(
        story_cutoff="evt-010",
        max_chars=4500,
        dynamic_state={"affinity": -10},
    ),
)

messages_for_model = compiled.messages
local_debug_only = compiled.debug
```

Harness 同事只需映射 `messages_for_model`：

- `messages[0]` 是共享模板编译出的 `system`；
- `messages[1]` 是未经信任的原始 `user`；
- 只进行一次 assistant 生成；
- `debug` 只能写本地日志，禁止发送给模型。

如果端侧 API 只能接受单字符串，应由 Harness 按目标模型的官方 Chat Template 序列化这两条消息，不应在本模块内硬编码 MiniCPM、Qwen 或其他模型的特殊标记。

## 预算策略

默认预算为 4500 字符，优先级为：

1. 身份、人格和硬约束；
2. 剧情截止点与动态状态；
3. 相关关系、事件、记忆。

可选项按相关度和重要性排序，超出预算便整项删除，不做可能破坏语义的半句截断。当调用者给出的预算小于必需层时，编译器仍保留必需层，并通过 `debug.budget_exceeded_by_mandatory=true` 报告；调用者应增加上下文预算，而不是删掉身份或知识边界。

## 当前限制

- 两张卡和 20 个事件只覆盖提供的六章，不代表整部作品设定。
- 首版检索使用中文字符 n-gram 与关键词，不处理同义词扩展；可通过 `StoryRetriever` 接口替换。
- 自动化测试验证授权内容和最终 Prompt，不调用生成模型，因此不评价模型最终文风质量。
- 动态状态当前由调用方传入并覆盖卡内默认值；本模块不自行总结长对话。
- 原文中玄谙的许多远古叙述来自角色自述，事件已按 `reported` 和置信度处理，不能视为作者层面的绝对真相。
