# Harness LLM 项目化与角色系统接入计划书

本文档基于当前两个已有模块制定后续改造计划：

- `harness_logic/harness_logic.py`：从 Android 项目提取出的 Python Harness 编排脚本。
- `character_system/`：短篇小说 NPC 角色卡、剧情事件、知识边界和 Prompt 编译系统。

目标分三步：

1. 将 `harness_logic.py` 扩展为一个可以接入真实 LLM 的完整 Python 项目。
2. 将 `character_system` 中的角色系统接入 Harness，使 Harness 可以按 NPC 身份编译 Prompt，并调用 LLM 完成角色化单轮或多轮生成。
3. 将角色能力抽象为可插拔的角色包机制，为后续端侧 LLM 游戏 SDK 保留持续扩展能力。

当前实现优先级调整为：

1. **角色包注册优先**：先让 Harness 能发现、校验和列出 `character_system` 以及后续新增角色包。
2. **角色对话优先**：在 mock backend 上先跑通 `character-prompt` / `character-chat`，验证角色 Prompt 编译、知识边界和 CLI/API 体验。
3. **Memory 优先**：先实现 session、turn log、短期 session memory 和显式长期 memory 写入边界。
4. **RAG 后置**：RAG 仍保留为重要能力，但应在角色对话和 Memory 稳定后实现。
5. **真实 LLM backend 后置**：OpenAI-compatible 和本地 GGUF backend 不应阻塞角色系统与 Memory 的核心链路验证；第一版继续用 mock backend 做 CI 和功能验收。

本文只做计划，不直接实现代码。

## 1. 当前现状

### 1.1 harness_logic 当前能力

当前 `harness_logic/harness_logic.py` 已经具备一套可运行的 Harness 雏形：

- `ModelInfo`：模型元数据，来自 Android `ModelInfo.kt`。
- `HarnessModelSpec`：通用模型描述，包含 family、capability、artifact、download source、runtime hints。
- `HarnessModelRegistry`：模型注册表，负责从 legacy model info 暴露 spec。
- `LlamaModelStore`：模型选择、本地模型路径、artifact 完整性检查、旧布局迁移。
- `LlamaDownloadManager`：生成 HuggingFace、ModelScope、Direct URL 下载计划。
- `HarnessBackend`：当前是 mock backend，不做真实推理。
- `LlamaBackendAdapter`：保留 Android adapter 形态，但 Python 里继承 mock backend。
- `HarnessFacade`：统一入口，封装模型、存储、下载和 backend 调用。
- CLI：支持 `list`、`spec`、`select`、`status`、`download-plan`、`migrate`、`touch-demo-files`、`load`、`prompt`、`delete`。

当前边界：

- 不调用 Android `LlamaEngine`。
- 不调用 JNI。
- 不加载真实 GGUF。
- 不真实下载模型。
- 不做真实 LLM 推理。
- `prompt` 只是 mock 输出。

### 1.2 character_system 当前能力

`character_system/` 已经是相对独立的角色 Prompt 编译模块。

核心数据和代码包括：

- `characters/*.json`：NPC 角色卡，目前包括 `lu_jiangxian` 和 `xuan_an`。
- `story/story_events.jsonl`：公共剧情事件，一份事件表供多个角色共享。
- `prompts/roleplay_system.prompt`：唯一共享 roleplay system prompt 模板。
- `runtime/prompt_compiler.py`：核心运行时编译器。
- `runtime/retrieval.py`：低依赖关键词检索器，可替换为 BM25 或向量检索。
- `runtime/knowledge_filter.py`：知识边界过滤，避免未来事件、越权知识、元问题进入 Prompt。
- `runtime/memory_retriever.py`：按授权事件召回角色个人经历。
- `runtime/validation.py`：角色卡、事件和引用校验。
- `tests/test_character_system.py`：验证 schema、知识边界、预算裁剪、注入隔离等行为。

核心 API：

```python
from pathlib import Path
from runtime import PromptCompiler, RuntimeContext

compiler = PromptCompiler(Path("character_system"))
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

输出契约：

- `compiled.messages[0]` 是可信 `system`。
- `compiled.messages[1]` 是未经信任的原始 `user`。
- `compiled.debug` 只允许写本地日志，不能发送给模型。
- Harness 只需要接收 `messages_for_model`，再按目标模型的 chat template 序列化或直接调用 chat API。

## 2. 总体目标架构

目标不是把 `character_system` 的逻辑复制进 Harness，而是让 Harness 调用它的稳定 Runtime API。

如果后续目标是端侧 LLM 游戏 SDK，角色不应是代码分支，而应是数据资产。Harness Core 只负责加载、校验、注册、编译和调用；新增角色时应主要新增角色包和剧情数据，而不是修改核心逻辑。

SDK 级目标分层：

```text
Game LLM SDK
  ├─ Model Runtime Layer
  │   ├─ llama.cpp / Android JNI / OpenAI-compatible / mock
  │   └─ 模型加载、生成、流式输出、停止词、chat template
  ├─ Harness Core
  │   ├─ 模型注册
  │   ├─ backend 调度
  │   ├─ session 管理
  │   ├─ memory 管理
  │   ├─ RAG 编排
  │   └─ 统一 chat / character chat API
  ├─ Character Runtime
  │   ├─ PromptCompiler
  │   ├─ 知识边界过滤
  │   ├─ 记忆检索
  │   └─ 预算裁剪
  ├─ Memory & RAG Layer
  │   ├─ 短期会话记忆
  │   ├─ 长期玩家/角色记忆
  │   ├─ 剧情知识库
  │   ├─ embedding / index
  │   └─ 检索、重排、预算注入
  ├─ Character Pack Registry
  │   ├─ 角色包扫描
  │   ├─ schema 校验
  │   ├─ 版本迁移
  │   └─ 角色元数据索引
  └─ Game State Adapter
      ├─ 场景
      ├─ 任务状态
      ├─ 亲近度 / 情绪 / 阵营
      └─ 游戏引擎运行时变量映射
```

推荐目标结构：

```text
harness_logic/
├── pyproject.toml
├── README.md
├── __init__.py
├── __main__.py
├── harness_logic.py
├── models.py
├── registry.py
├── store.py
├── download.py
├── backend.py
├── backends/
│   ├── __init__.py
│   ├── mock_backend.py
│   ├── llama_cpp_backend.py
│   └── openai_compatible_backend.py
├── chat_template.py
├── session.py
├── memory.py
├── memory_store.py
├── rag.py
├── retrievers.py
├── embeddings.py
├── vector_store.py
├── character_adapter.py
├── character_pack.py
├── character_registry.py
├── game_state.py
├── facade.py
├── cli.py
├── data/
│   └── models/
├── tests/
│   ├── test_registry.py
│   ├── test_store.py
│   ├── test_chat_template.py
│   ├── test_memory.py
│   ├── test_rag.py
│   ├── test_character_adapter.py
│   ├── test_character_registry.py
│   ├── test_game_state.py
│   └── test_cli.py
└── HARNESS_LLM_CHARACTER_INTEGRATION_PLAN.md
```

当前项目采用 `harness_logic/` 目录本身作为 package 根，`pyproject.toml` 通过 `package-dir` 指向该目录；不再额外嵌套 `harness_logic/harness_logic/`。兼容入口 `harness_logic.py` 保留为薄 wrapper。

目标运行链路：

```text
用户输入
  -> Harness CLI / API
      -> CharacterPromptAdapter
          -> character_system.PromptCompiler
              -> messages: [system, user]
      -> MemoryManager.retrieve()
      -> RagPipeline.retrieve()
      -> PromptContextBuilder 合并角色 prompt / memory / rag
      -> HarnessFacade.chat(messages)
          -> selected HarnessModelSpec
          -> BackendFactory
          -> LLMBackend.generate_chat(messages, options)
              -> llama.cpp / OpenAI-compatible API / mock
      -> assistant response
      -> SessionStore 更新对话摘要或日志
```

关键原则：

- `character_system` 负责角色知识、Prompt 编译和授权边界。
- `harness_logic` 负责模型选择、模型文件、backend、chat template、生成参数和会话。
- `CharacterPackRegistry` 负责发现、校验和注册角色包。
- `GameStateAdapter` 负责把游戏状态映射为 `RuntimeContext.dynamic_state`。
- `MemoryManager` 负责短期会话记忆、长期玩家/角色记忆的写入、召回和摘要。
- `RagPipeline` 负责剧情知识库、设定文档、任务资料等外部知识检索，并把结果安全地注入 Prompt。
- `debug` 只能进入本地日志，不能进入 LLM prompt。
- 用户原始输入只作为 `user` message，不插值进可信 system prompt。
- 真实 backend 必须支持 `messages`，不能只接收裸字符串。

核心设计约束：

- 模型可换：角色包不绑定特定模型。
- 角色可插拔：新增角色不改 Harness Core。
- 剧情知识可检索：事件和记忆通过统一 retriever 进入 Prompt。
- 记忆可沉淀：会话事实、玩家偏好、角色关系变化可进入长期 memory。
- RAG 可替换：首版关键词检索，后续可替换 BM25、向量检索或混合检索。
- 游戏状态可注入：场景、任务、亲近度、情绪由游戏运行时传入。
- Prompt 编译统一：不同角色复用同一编译流程。
- Harness 只做编排：不直接拼角色卡，不越过知识边界。

## 2.1 角色包扩展性方案

### 2.1.1 角色包是内容资产

为了支持后续游戏 SDK 中持续新增 NPC，角色应以角色包形式存在：

```text
character_packs/
  lu_jiangxian/
    pack.json
    character.json
    relationships.json
    memories.jsonl
    story_events.jsonl
    prompts/
      roleplay_system.prompt
    migrations/
      1.0.0_to_1.1.0.py

  xuan_an/
    pack.json
    character.json
    relationships.json
    memories.jsonl
    story_events.jsonl
    prompts/
      roleplay_system.prompt
```

当前 `character_system/` 可以视为第一版内置角色包集合。后续可以保持兼容：

```text
character_system/
  characters/
  story/
  prompts/
  runtime/
```

但 SDK 抽象层不应写死 `character_system/characters/*.json`，而应通过 `CharacterPackRegistry` 扫描一个或多个角色包根目录。

### 2.1.2 pack.json 契约

每个角色包建议增加 `pack.json`：

```json
{
  "pack_id": "builtin_novel_test",
  "schema_version": "1.0.0",
  "display_name": "短篇小说测试角色包",
  "characters": [
    {
      "character_id": "lu_jiangxian",
      "display_name": "陆江仙",
      "aliases": ["鉴身", "玄鉴"],
      "character_file": "character.json",
      "story_events_file": "story_events.jsonl",
      "prompt_template": "prompts/roleplay_system.prompt"
    }
  ],
  "default_cutoff": "evt-018",
  "locale": "zh-CN"
}
```

角色包必须声明：

- `pack_id`
- `schema_version`
- 可用角色列表
- 每个角色的数据文件
- story events 文件
- prompt 模板
- 默认剧情截止点
- locale

### 2.1.3 CharacterSpec

Harness 不应直接依赖某个 JSON 文件内部细节。建议抽象出 SDK 级 `CharacterSpec`：

```python
@dataclass
class CharacterSpec:
    character_id: str
    display_name: str
    aliases: list[str]
    pack_id: str
    schema_version: str
    default_cutoff: str | None
    supported_locales: list[str]
    dynamic_state_schema: dict[str, Any] | None = None
```

`CharacterSpec` 只用于注册、展示和选择；真正 Prompt 编译仍交给角色 runtime。

### 2.1.4 CharacterPackRegistry

新增 `character_registry.py`：

```python
class CharacterPackRegistry:
    def __init__(self, roots: list[Path]):
        self.roots = roots

    def scan(self) -> list[CharacterSpec]:
        ...

    def find(self, character_id: str) -> CharacterSpec | None:
        ...

    def resolve_runtime_root(self, character_id: str) -> Path:
        ...
```

它的职责：

- 扫描角色包目录。
- 读取 `pack.json`。
- 校验 schema version。
- 建立 `character_id -> CharacterSpec` 索引。
- 检查重复角色 ID。
- 提供给 UI / CLI 角色列表。

新增角色的理想流程：

```text
新增角色包目录
  -> 写 pack.json / character.json / events / memories
  -> 运行 schema 校验
  -> CharacterPackRegistry 自动发现
  -> UI 或 CLI 可以选择该角色
  -> PromptCompiler 编译
  -> Harness 调用 backend
```

核心要求：新增角色不修改 `HarnessFacade`，不修改 backend，不修改模型注册。

## 2.2 Memory 与 RAG 扩展方案

端侧 LLM 游戏 SDK 需要同时支持“角色知道什么”和“角色记住什么”。这两类能力不能混为一谈：

- 角色知识：来自角色包、剧情事件、世界设定，是内容作者预先定义的事实。
- 会话记忆：来自玩家和角色的历史互动，是运行时逐步产生的事实。
- RAG 知识：来自外部知识库、任务文档、图鉴、道具说明、世界百科等可检索资料。

建议将 memory 和 RAG 抽象成独立层，由 Harness 编排，不直接写入角色卡。

### 2.2.1 Memory 类型划分

Memory 至少分四类：

| 类型 | 来源 | 生命周期 | 是否进入角色包 | 示例 |
| --- | --- | --- | --- | --- |
| `session_memory` | 当前会话最近对话 | 单次会话 | 否 | 玩家刚刚说过自己的选择 |
| `summary_memory` | 长对话摘要 | 会话或存档 | 否 | 玩家已与角色达成临时同盟 |
| `profile_memory` | 玩家偏好和长期事实 | 跨会话 | 否 | 玩家喜欢直接回答、不喜欢谜语 |
| `character_memory` | 角色对玩家的长期印象 | 跨会话、按角色隔离 | 否 | 陆江仙对玩家亲近度上升 |

`character_system` 当前的 `episodic_memory` 是“角色卡内置记忆”，属于内容资产；上表中的 memory 是运行时产生的 SDK memory。两者都可进入 Prompt，但来源和权限不同。

### 2.2.2 Memory 数据结构

建议新增 `memory.py`：

```python
@dataclass
class MemoryRecord:
    memory_id: str
    scope: str
    owner_id: str | None
    character_id: str | None
    session_id: str | None
    kind: Literal[
        "session_memory",
        "summary_memory",
        "profile_memory",
        "character_memory",
        "world_memory",
    ]
    text: str
    importance: float
    confidence: float
    created_at: str
    updated_at: str
    expires_at: str | None = None
    source_turn_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
```

关键字段说明：

- `scope`：隔离范围，例如 `global`、`player`、`character`、`session`、`save_slot`。
- `owner_id`：玩家或账号 ID，没有账号时可用本地 profile ID。
- `character_id`：角色相关记忆必须绑定角色，防止 A 角色记忆泄露给 B 角色。
- `importance`：用于召回排序和摘要保留。
- `confidence`：用于表达确定性，不确定记忆进入 Prompt 时要保留限定。
- `expires_at`：临时记忆过期控制。

### 2.2.3 MemoryStore

建议新增 `memory_store.py`：

```python
class MemoryStore(Protocol):
    def append(self, record: MemoryRecord) -> None:
        ...

    def search(
        self,
        query: str,
        scope: MemoryScope,
        limit: int,
    ) -> list[RetrievedMemory]:
        ...

    def update(self, memory_id: str, patch: dict[str, Any]) -> None:
        ...

    def delete(self, memory_id: str) -> None:
        ...
```

其中 `MemoryScope`、`RetrievedMemory` 是计划新增的检索参数和返回结构，应包含 player/session/character/save-slot 等隔离信息。

第一版实现：

- `JsonlMemoryStore`：无依赖，写入 `<root>/memory/*.jsonl`。
- `InMemoryStore`：测试用。

后续实现：

- `SqliteMemoryStore`：端侧正式存储，支持索引和事务。
- `VectorMemoryStore`：向量召回，适合长期记忆。
- `EncryptedMemoryStore`：涉及玩家隐私时使用。

### 2.2.4 MemoryManager

`MemoryManager` 负责把存储、召回、摘要和写入策略组合起来：

```python
class MemoryManager:
    def retrieve_for_turn(
        self,
        character_id: str,
        session_id: str,
        player_input: str,
        game_state: GameState,
        budget: int,
    ) -> list[MemoryRecord]:
        ...

    def observe_turn(
        self,
        session: CharacterSession,
        user_input: str,
        assistant_output: str,
    ) -> list[MemoryWriteCandidate]:
        ...
```

其中 `MemoryWriteCandidate` 是计划新增的候选写入结构，用于区分“可自动保存的短期记忆”和“需要确认的长期记忆”。

第一版不要让模型自动写长期记忆，避免把幻觉固化。建议：

- 默认只写 `session_memory` 和完整 turn log。
- `summary_memory` 可由手动命令或受控总结器生成。
- `profile_memory` 和 `character_memory` 必须经过规则校验或用户/游戏确认。

### 2.2.5 RAG 类型划分

RAG 用于检索“外部知识”，不等同于 memory。

建议分三类知识库：

| 类型 | 来源 | 典型用途 |
| --- | --- | --- |
| `story_rag` | 剧情事件、章节摘要、世界设定 | NPC 根据当前剧情回答 |
| `game_rag` | 道具、任务、地图、技能、机制说明 | 游戏内问答和任务提示 |
| `developer_rag` | SDK 文档、调试手册 | 开发调试，不进入正式角色对话 |

正式角色对话默认只允许 `story_rag` 和经过白名单授权的 `game_rag`。`developer_rag` 禁止进入玩家可见的角色对话。

### 2.2.6 RagPipeline

建议新增 `rag.py`：

```python
@dataclass
class RagDocument:
    doc_id: str
    source: str
    text: str
    metadata: dict[str, Any]

@dataclass
class RetrievedContext:
    doc_id: str
    text: str
    score: float
    source: str
    metadata: dict[str, Any]

class RagPipeline:
    def retrieve(
        self,
        query: str,
        character: CharacterSpec | None,
        game_state: GameState | None,
        policy: RagPolicy,
        limit: int,
    ) -> list[RetrievedContext]:
        ...
```

其中 `RagPolicy` 是计划新增的权限策略结构，应包含 namespace 白名单、story cutoff、角色 visibility、是否允许 developer/debug 文档等约束。

RAG pipeline 至少包含：

```text
query
  -> query normalizer
  -> retriever
  -> permission filter
  -> reranker
  -> deduplicator
  -> budget selector
  -> prompt formatter
```

### 2.2.7 Retriever 与索引策略

第一版检索不应直接引入重依赖。建议分层：

```python
class Retriever(Protocol):
    def index(self, documents: list[RagDocument]) -> None:
        ...

    def search(self, query: str, limit: int) -> list[RetrievedContext]:
        ...
```

实现顺序：

1. `KeywordRetriever`：复用当前 `character_system/runtime/retrieval.py` 的思路，零依赖。
2. `Bm25Retriever`：如果引入轻量依赖或自实现 BM25。
3. `VectorRetriever`：接 embedding 模型和向量库。
4. `HybridRetriever`：关键词 + 向量混合召回。

端侧 SDK 优先考虑：

- 小型本地 embedding 模型。
- SQLite FTS。
- 本地向量索引。
- 构建期预索引，运行期只加载索引。

### 2.2.8 Embedding 与 VectorStore

建议新增：

- `embeddings.py`
- `vector_store.py`

接口：

```python
class EmbeddingBackend(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...

class VectorStore(Protocol):
    def upsert(self, vectors: list[VectorRecord]) -> None:
        ...

    def search(self, vector: list[float], limit: int) -> list[VectorHit]:
        ...
```

第一版可以不实现 embedding，只保留接口和关键词检索。这样不会阻塞角色系统接入。

### 2.2.9 Prompt 注入顺序与预算

角色对话的上下文建议按优先级进入 Prompt：

```text
1. 角色身份、人格、硬约束
2. 剧情 cutoff 和知识边界
3. 当前 GameState / dynamic_state
4. 本轮授权剧情事实
5. 角色内置 episodic memory
6. 运行时 summary_memory
7. 本轮召回的 session / profile / character memory
8. 本轮 RAG 召回片段
9. 用户原始输入
```

预算不足时删除顺序：

```text
RAG 低分片段
  -> 低重要度运行时 memory
  -> 低相关剧情事实
  -> 对话摘要压缩版
  -> 保留必需角色身份和硬约束
```

绝不能为了预算删除：

- 角色身份。
- 知识边界。
- prompt injection 防护。
- 当前 `user` 输入。

### 2.2.10 Memory / RAG 安全边界

Memory 和 RAG 必须遵守角色知识边界：

- A 角色私有记忆不能召回给 B 角色。
- 玩家 profile memory 需要按存档或账号隔离。
- 未来剧情 RAG 不能在 cutoff 之前进入 Prompt。
- developer/debug 文档不能进入正式角色对话。
- 不确定 memory 必须带 `confidence`，进入 Prompt 时保留“不确定”措辞。
- RAG 片段必须带来源 ID，便于调试和审计。

Memory 写入也要谨慎：

- 不把模型推断自动当事实。
- 不把用户提示注入内容写成长期偏好。
- 不把一次性情绪写成永久人格关系。
- 重要长期记忆应支持确认、撤销、过期和覆盖。

## 3. 第一阶段：独立化 harness_logic 项目基线

### 3.1 目标

第一阶段不再是“准备把单文件拆成项目”，而是确认当前 `harness_logic` 已经形成可独立运行的 Python 子项目，并把它作为后续 LLM、角色、Memory、RAG 接入的稳定基线。

当前第一阶段目标调整为：

1. 保持 `harness_logic/` 目录自身作为 Python package 根。
2. 保留 `harness_logic.py`、`__main__.py`、`run.sh` 三类入口。
3. 让 `run.sh` 默认运行状态和模型文件独立存放在 `harness_logic/data/`，不复用仓库根目录 `models/`。
4. 保留 Android Harness 迁移过来的模型注册、artifact、下载计划、模型选择和 facade 骨架。
5. 保留 mock backend，确保没有真实模型 runtime 时也能验证调用链路。
6. 为后续 `character_registry`、`character_pack`、`game_state`、`memory`、`rag`、`chat_template` 等模块留下可扩展边界。
7. 用单元测试和 CLI 命令验证项目化基线。

### 3.2 当前已落地模块

当前项目已经按职责拆分为：

| 模块 | 当前职责 | 状态 |
| --- | --- | --- |
| `models.py` | `ModelInfo`、`HarnessModelSpec`、artifact、capability、state 等数据结构 | 已实现 |
| `registry.py` | 内置模型清单、`ModelInfo -> HarnessModelSpec` 转换、模型查询 | 已实现 |
| `store.py` | 选中模型状态、本地 artifact 路径、完整性检查、旧布局迁移 | 已实现 |
| `download.py` | HuggingFace / ModelScope / Direct 下载计划生成 | 已实现计划生成，未真实下载 |
| `backend.py` | mock runtime 基类，模拟 load、prompt、vision 状态 | 已实现 mock 行为 |
| `backends/mock_backend.py` | `MockBackend` 和 `LlamaBackendAdapter` 兼容名 | 已实现 |
| `facade.py` | 对外统一封装模型、存储、下载和 backend 调用 | 已实现 |
| `cli.py` | `list`、`spec`、`select`、`status`、`download-plan`、`migrate`、`touch-demo-files`、`load`、`prompt`、`delete` | 已实现 |
| `chat_template.py` | 后续 chat template 渲染边界 | 占位 |
| `character_registry.py` | 后续角色包发现和注册边界 | 占位 |
| `character_pack.py` | 后续角色包元数据边界 | 占位 |
| `game_state.py` | 后续游戏状态适配边界 | 占位 |
| `memory.py` | 后续运行时 memory 边界 | 占位 |
| `rag.py` | 后续 RAG pipeline 边界 | 占位 |

### 3.3 独立运行目录

第一阶段要求 `run.sh` 的默认状态和模型目录使用 `harness_logic` 项目内相对运行目录：

```text
harness_logic/data/.harness_state.json
harness_logic/data/models/<model_id>/<artifact_file>
```

这和 Android App 的 `filesDir/models/<model_id>/` 在结构上对齐，但二者互不复用。`harness_logic/data/` 下的真实模型、状态文件和 mock artifact 不应提交到 Git。

默认 CLI：

```bash
python -m harness_logic status
```

应直接检查当前工作目录下的 `models/...`。如需临时切换运行根，可以继续显式传相对目录：

```bash
python -m harness_logic --root ./runtime/harness-test status
```

`run.sh` 默认使用：

```text
harness_logic/data/
```

### 3.4 项目文件

`pyproject.toml` 初期可不强制引入重依赖。真实 LLM backend 依赖应做 optional extra：

```toml
[project.optional-dependencies]
llama-cpp = ["llama-cpp-python"]
server = ["fastapi", "uvicorn"]
dev = ["pytest"]
```

第一阶段已经具备：

- `pyproject.toml`
- `README.md`
- `__init__.py`
- `__main__.py`
- `harness_logic.py` 兼容入口
- `run.sh` 交互入口
- `tests/`

### 3.5 保留兼容入口

`harness_logic/harness_logic.py` 保留为兼容入口：

```python
from harness_logic.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

这样已有命令仍可运行：

```bash
python harness_logic/harness_logic.py list
```

同时支持模块方式：

```bash
python -m harness_logic list
```

### 3.6 第一阶段不包含的内容

第一阶段只保证项目骨架和 mock 调用链路，不包含：

- 真实 GGUF 下载。
- 真实 LLM 推理。
- `generate_chat(messages, options)` 标准 chat 接口。
- llama.cpp / llama-cpp-python backend。
- OpenAI-compatible backend。
- 角色 Prompt 接入。
- Session、Memory、RAG 的真实读写和检索。

这些内容从后续优先阶段开始逐步实现，其中角色包注册、角色对话和 Memory 优先于 RAG 与真实 backend。

## 4. 后置能力：定义真实 LLM Backend 接口

### 4.1 目标

把当前 mock backend 抽象成统一接口，允许接入多种 LLM runtime。

建议新增协议：

```python
class LLMBackend(Protocol):
    state: LlamaState

    def load_model(self, model_files: LlamaModelFiles, spec: HarnessModelSpec) -> None:
        ...

    def unload_model(self) -> None:
        ...

    def generate_chat(
        self,
        messages: list[dict[str, str]],
        options: GenerationOptions,
    ) -> Iterator[str]:
        ...
```

`send_user_prompt(message: str)` 作为低层兼容方法保留，但角色系统接入应使用 `generate_chat(messages)`。

### 4.2 GenerationOptions

新增统一生成参数：

```python
@dataclass
class GenerationOptions:
    max_tokens: int = 1024
    temperature: float = 0.7
    top_p: float = 0.9
    stop: list[str] = field(default_factory=list)
    stream: bool = True
    seed: int | None = None
```

可从 `HarnessModelSpec.runtime_hints` 生成默认值。

### 4.3 Backend 类型

建议分三类接入：

#### MockBackend

继续保留，用于测试和无模型演示。

用途：

- CLI 冒烟测试。
- Character adapter 测试。
- CI 不需要下载大模型。

#### LlamaCppBackend

接入本地 GGUF，优先考虑 `llama-cpp-python`。

职责：

- 加载 `llm` artifact。
- 对 vision 模型，先只记录 `vision_projector` 路径；是否真实支持多模态取决于所选 binding。
- 支持 chat messages。
- 支持 streaming。
- 支持 stop tokens。

注意：

- `llama-cpp-python` 对不同多模态模型的 mmproj 支持需要单独验证。
- MiniCPM-V / VoxCPM2 可能需要 Android 项目中 `llama.cpp-omni` 的特殊能力，不能假设普通 binding 直接支持。
- 第一版真实 LLM 项目建议先以 text-only 模型跑通，例如 `llama-3.2-1b-instruct` 或 `qwen3-0.6b`。

#### OpenAICompatibleBackend

接入本地或远端 OpenAI-compatible chat completion server。

用途：

- 快速验证角色系统效果。
- 绕过本地 GGUF 多模态支持问题。
- 支持 vLLM、llama.cpp server、Ollama 兼容层或其他本地服务。

接口：

```text
POST /v1/chat/completions
messages: [...]
stream: true/false
```

配置建议：

```json
{
  "backend": "openai_compatible",
  "base_url": "http://127.0.0.1:8000/v1",
  "api_key": "optional",
  "model": "local-model"
}
```

## 5. 后置能力：Chat Template 与消息序列化

### 5.1 为什么需要 Chat Template

`character_system` 输出的是标准 chat messages：

```json
[
  {"role": "system", "content": "..."},
  {"role": "user", "content": "..."}
]
```

如果 backend 是 OpenAI-compatible，可以直接传 messages。

如果 backend 是裸 llama.cpp generate，需要把 messages 序列化成模型需要的 prompt 字符串。这个逻辑应属于 Harness，而不是 `character_system`。

### 5.2 建议设计

新增 `chat_template.py`：

```python
class ChatTemplate(Protocol):
    def render(self, messages: list[dict[str, str]]) -> str:
        ...
```

内置模板：

- `openai_passthrough`：不序列化，直接交给 chat API。
- `generic_chatml`
- `llama3`
- `qwen`
- `minicpm`

第一阶段只需要支持：

- OpenAI-compatible 直接传 messages。
- Mock backend 直接读取 messages。
- Llama.cpp text-only 模型使用一个明确模板。

### 5.3 模板选择

在 `HarnessRuntimeHints` 或新增字段中加入：

```python
chat_template: str | None = None
```

或者在 backend config 中覆盖：

```json
{
  "model_id": "qwen3-0.6b",
  "chat_template": "qwen"
}
```

## 6. 优先能力：接入 character_system 与角色包机制

### 6.1 新增 CharacterPromptAdapter

建议新增 `character_adapter.py`：

```python
@dataclass
class CharacterTurnRequest:
    character_id: str
    user_input: str
    story_cutoff: str | None = None
    max_chars: int = 4500
    dynamic_state: dict[str, Any] | None = None
    conversation_summary: str = ""
    top_k: int = 8

@dataclass
class CharacterTurn:
    messages: list[dict[str, str]]
    debug: dict[str, Any]
```

核心方法：

```python
class CharacterPromptAdapter:
    def __init__(self, registry: CharacterPackRegistry):
        self.registry = registry

    def compile_turn(self, request: CharacterTurnRequest) -> CharacterTurn:
        runtime_root = self.registry.resolve_runtime_root(request.character_id)
        compiler = PromptCompiler(runtime_root)
        compiled = compiler.build_npc_prompt(
            request.character_id,
            request.user_input,
            RuntimeContext(
                story_cutoff=request.story_cutoff,
                max_chars=request.max_chars,
                dynamic_state=request.dynamic_state,
                conversation_summary=request.conversation_summary,
                top_k=request.top_k,
            ),
        )
        return CharacterTurn(messages=compiled.messages, debug=compiled.debug)
```

注意：示例中的 `PromptCompiler(runtime_root)` 是最小方案。正式项目中应缓存 compiler，并在角色包变更时失效，避免每轮重新加载事件和模板。

### 6.2 新增 CharacterPackRegistry

`CharacterPromptAdapter` 不应写死 `character_system/`，而应通过 `CharacterPackRegistry` 解析角色来源。

第一版兼容当前目录：

```text
character_system/
  characters/lu_jiangxian.json
  characters/xuan_an.json
  story/story_events.jsonl
  prompts/roleplay_system.prompt
```

可以把它注册成一个内置 pack：

```python
registry = CharacterPackRegistry.builtin(
    root=Path("character_system"),
    pack_id="builtin_novel_test",
)
```

后续扩展到多包：

```python
registry = CharacterPackRegistry([
    Path("character_system"),
    Path("game_content/character_packs"),
    Path("dlc/characters"),
])
```

### 6.3 角色新增流程

新增角色不应修改 `HarnessFacade` 或 backend。流程应是：

```text
1. 新增角色 JSON / 角色包
2. 新增或复用 story_events.jsonl
3. 新增 memories / relationships
4. 运行 validate
5. CharacterPackRegistry 扫描到角色
6. CLI/UI 可选择该角色
7. CharacterPromptAdapter 编译角色 messages
8. Harness 调用当前模型生成
```

对于 SDK，建议把“角色包构建”和“运行时加载”分开：

- 构建期：严格校验 schema、证据引用、事件引用、重复 ID。
- 运行期：只加载已通过校验的角色包，避免端侧启动时做昂贵检查。

### 6.4 角色包版本迁移

所有角色包必须带 `schema_version`。当 schema 升级时，不直接破坏旧角色包，而是提供迁移链：

```text
1.0.0 -> 1.1.0 -> 1.2.0
```

Harness 启动时的策略：

- 支持当前 schema：直接加载。
- 支持旧 schema 且有迁移器：迁移后加载。
- 不支持 schema：拒绝加载该角色包，并给出明确错误。

迁移应优先作为构建期工具执行，不建议在游戏运行时频繁改写内容资产。

### 6.5 Facade 新增角色生成方法

在 `HarnessFacade` 中新增：

```python
def generate_character_turn(
    self,
    request: CharacterTurnRequest,
    options: GenerationOptions | None = None,
) -> Iterator[str]:
    turn = self.character_adapter.compile_turn(request)
    self.log_debug(turn.debug)
    yield from self.backend.generate_chat(turn.messages, options or self.default_options())
```

约束：

- `turn.debug` 只能写入本地日志或返回给 CLI `--debug`。
- 不得把 `debug` 拼入 `messages`。
- 角色身份、知识边界、未来事件过滤由 `character_system` 完成。
- Harness 只负责发送编译后的 messages。
- Harness 不关心角色 JSON 的内部字段，只处理 `CharacterTurnRequest`、`messages` 和 `debug`。

### 6.6 CLI 设计

新增命令：

```bash
python -m harness_logic character-list
python -m harness_logic character-pack validate --path character_system
python -m harness_logic character-prompt \
  --character lu_jiangxian \
  --input "玄谙究竟是什么？" \
  --cutoff evt-010 \
  --debug

python -m harness_logic character-chat \
  --character lu_jiangxian \
  --input "玄谙究竟是什么？" \
  --cutoff evt-010 \
  --model llama-3.2-1b-instruct
```

命令职责：

- `character-list`：列出所有注册角色包中的可用角色。
- `character-pack validate`：校验角色包数据、schema、事件和引用。
- `character-prompt`：只编译并输出 messages，不调用 LLM。
- `character-chat`：编译 messages 并调用当前 backend 生成 assistant。

### 6.7 Python API 设计

目标 API：

```python
from pathlib import Path
from harness_logic import HarnessFacade, CharacterTurnRequest, CharacterPackRegistry

registry = CharacterPackRegistry([
    Path("character_system"),
    Path("game_content/character_packs"),
])

harness = HarnessFacade(
    root_dir=Path("."),
    character_registry=registry,
)

harness.set_selected_model("llama-3.2-1b-instruct")
harness.load_selected_model()

for chunk in harness.generate_character_turn(
    CharacterTurnRequest(
        character_id="lu_jiangxian",
        user_input="玄谙究竟是什么？",
        story_cutoff="evt-010",
    )
):
    print(chunk, end="")
```

### 6.8 UI / 游戏 SDK 视角

对原 Android Demo 或未来游戏 SDK，UI 不应把“模型”和“角色”混成一个选择项。

推荐 UI 概念：

```text
模型选择
  - llama-3.2-1b-instruct
  - qwen3-0.6b
  - minicpm5-0.9b

对话模式
  - 普通对话
  - 角色对话

角色对话设置
  - 角色：陆江仙 / 玄谙 / DLC 角色
  - 剧情截止点：evt-018
  - 场景：洞华天青铜门外
  - 亲近度：-20
  - 情绪：克制而警惕
```

这样同一个角色可以运行在不同模型上，同一个模型也可以用于普通对话或角色对话。

## 7. 优先能力：会话与 Memory；后置能力：RAG

### 7.1 当前 character_system 的边界

`character_system` 支持传入：

- `conversation_summary`
- `dynamic_state`

但它不自行总结长对话，也不负责会话存储、运行时 memory 写入或外部知识库 RAG。

这部分应该由 Harness 负责。

### 7.2 新增 SessionStore

建议新增 `session.py`：

```python
@dataclass
class ConversationTurn:
    role: str
    content: str
    timestamp: str

@dataclass
class CharacterSession:
    session_id: str
    character_id: str
    character_pack_id: str
    story_cutoff: str
    selected_model_id: str
    turns: list[ConversationTurn]
    conversation_summary: str = ""
    dynamic_state: dict[str, Any] = field(default_factory=dict)
```

存储位置：

```text
<root>/sessions/<session_id>.json
```

### 7.3 新增 MemoryManager

建议新增 `memory.py`、`memory_store.py`，并由 `MemoryManager` 提供统一 API。

CLI/API 入口：

```bash
python -m harness_logic memory-list --session <id>
python -m harness_logic memory-search --character lu_jiangxian --query "玄谙"
python -m harness_logic memory-add \
  --character lu_jiangxian \
  --kind character_memory \
  --text "玩家曾帮助陆江仙保守洞华天秘密" \
  --importance 0.8
python -m harness_logic memory-delete --memory-id <id>
```

第一版策略：

- 自动保存完整 turn log。
- 自动写短期 `session_memory`。
- 不自动写长期 `profile_memory` / `character_memory`。
- 长期记忆需要显式 API、游戏事件或人工确认写入。

### 7.4 长对话摘要策略

第一版不要自动调用 LLM 总结，避免新增不可控行为。先提供手动更新：

```bash
python -m harness_logic session-summary set --session xxx --text "..."
```

第二版再增加：

- 使用同一 backend 总结最近 N 轮。
- 摘要也必须走知识边界，不允许把越权信息注入角色。
- 摘要写入 `RuntimeContext.conversation_summary`。

摘要写入 memory 时建议使用 `summary_memory`，并记录来源 turn 范围。

### 7.5 新增 RagPipeline

建议新增 `rag.py`、`retrievers.py`、`embeddings.py`、`vector_store.py`。

CLI/API 入口：

```bash
python -m harness_logic rag-index \
  --source character_system/story/story_events.jsonl \
  --namespace story

python -m harness_logic rag-search \
  --namespace story \
  --query "青诣元心仪"

python -m harness_logic character-chat \
  --character lu_jiangxian \
  --input "青诣元心仪到底是什么？" \
  --cutoff evt-018 \
  --rag story \
  --memory on
```

第一版策略：

- `story_events.jsonl` 走结构化剧情检索。
- 普通文档走关键词检索。
- RAG 结果进入 Prompt 前必须经过权限过滤和预算裁剪。
- debug 中记录 `retrieved_context_ids`，但不把 debug 发给模型。

### 7.6 PromptContextBuilder

为了避免 `CharacterPromptAdapter`、`MemoryManager`、`RagPipeline` 各自拼 Prompt，建议新增 `PromptContextBuilder`：

```python
class PromptContextBuilder:
    def build(
        self,
        character_turn: CharacterTurn,
        memories: list[MemoryRecord],
        rag_contexts: list[RetrievedContext],
        budget: PromptBudget,
    ) -> PromptContext:
        ...
```

其中 `PromptBudget` 是计划新增的预算结构，用于声明总上下文预算、各 section 优先级和裁剪顺序。

它负责：

- 合并角色 system prompt、memory、RAG。
- 按优先级裁剪。
- 保证 `user` 原始输入仍是独立 message。
- 保证 debug 不进入 messages。

如果第一版不想改 `character_system.PromptCompiler`，可以采用最小实现：

```text
compiled.messages[0].content
  + "\n\n【运行时记忆】\n..."
  + "\n\n【本轮可用资料】\n..."
```

但长期应把 memory / RAG 作为独立可控 section，由统一模板和预算器管理。

### 7.7 GameStateAdapter 与 dynamic_state 更新

端侧游戏 SDK 不能假设所有游戏都使用同一套状态字段。Harness 应提供 `GameStateAdapter`，把不同游戏引擎或玩法系统的运行时状态映射到角色 runtime 能理解的 `dynamic_state`。

建议新增：

```python
@dataclass
class GameState:
    scene: str | None = None
    quest_state: str | None = None
    affinity: int | None = None
    emotion: dict[str, Any] | None = None
    faction: str | None = None
    inventory_flags: dict[str, bool] = field(default_factory=dict)
    world_flags: dict[str, Any] = field(default_factory=dict)


class GameStateAdapter(Protocol):
    def to_dynamic_state(
        self,
        character: CharacterSpec,
        state: GameState,
    ) -> dict[str, Any]:
        ...
```

第一版可以提供默认映射：

```text
GameState.scene        -> dynamic_state.scene
GameState.quest_state  -> dynamic_state.quest_state
GameState.affinity     -> dynamic_state.affinity
GameState.emotion      -> dynamic_state.emotion
```

更复杂的游戏项目可以实现自己的 adapter，例如：

- Unity adapter
- Unreal adapter
- Android demo adapter
- 自定义 RPG 状态 adapter

这样角色系统只消费标准 `dynamic_state`，不直接依赖游戏引擎。

第一版同时支持 CLI/API 直接传入 JSON：

```bash
python -m harness_logic character-chat \
  --character lu_jiangxian \
  --input "你现在在哪里？" \
  --dynamic-state '{"scene":"临时测试场景","emotion":{"intensity":0.1}}'
```

后续再增加规则引擎或外部游戏状态适配器。

## 8. 后置能力：下载与模型管理完善

### 8.1 当前下载计划与真实下载分离

当前 `download-plan` 已能生成 URL，但不下载。

后续可以新增真实下载器：

- 支持 HF / ModelScope / Direct。
- 支持断点续传。
- 支持 MD5 校验。
- 支持 `.tmp` 文件。
- 支持多源竞速。

这部分可以参考 Android `LlamaEngine.downloadModels()`，但不要一开始就完整复刻。建议优先级：

1. 单源 direct 下载。
2. HF / ModelScope URL 下载。
3. MD5 校验。
4. 断点续传。
5. 多源竞速。

### 8.2 模型准备状态

新增命令：

```bash
python -m harness_logic model-status
python -m harness_logic model-download --model llama-3.2-1b-instruct
python -m harness_logic model-verify --model minicpm-v-4_6-instruct
```

角色系统本身不应关心模型文件是否存在。

## 9. 测试计划

### 9.1 保留 character_system 原测试

继续运行：

```bash
python -m unittest discover -s character_system/tests -v
```

这验证角色卡、事件、知识边界、预算裁剪、提示注入隔离等行为。

### 9.2 Harness 单元测试

新增：

- registry 测试：所有 `AVAILABLE_MODELS` 能生成 spec。
- store 测试：选中模型、artifact 路径、完整性检查。
- download plan 测试：HF / MS / Direct URL 正确展开。
- backend mock 测试：load、generate_chat、state 流转。
- chat template 测试：system/user 顺序正确，特殊 token 不错位。
- memory store 测试：append、search、delete、scope 隔离。
- memory manager 测试：短期记忆写入、长期记忆不自动固化、confidence 保留。
- RAG 测试：index、search、权限过滤、重复片段去重。
- prompt context builder 测试：角色 prompt、memory、RAG 的预算顺序正确。
- character registry 测试：角色包扫描、重复 ID 拒绝、schema version 检查。
- game state adapter 测试：游戏状态稳定映射到 `dynamic_state`。

### 9.3 Character adapter 测试

重点测试：

- `compile_turn()` 输出 `system` + `user` 两条消息。
- prompt injection 留在 user message，不进入 system。
- `debug` 不进入 messages。
- 未来事件被过滤。
- `story_cutoff` 改变时，允许事件集合随之变化。
- `character_id` 通过 `CharacterPackRegistry` 解析，而不是写死当前目录。
- 新增角色包后，无需修改 `HarnessFacade` 即可被发现。
- 不同角色包的 prompt template、events 和 cutoff 不互相污染。
- memory 召回不能突破角色 `story_cutoff`。
- RAG 召回不能把 developer/debug 文档注入正式角色对话。

### 9.4 端到端测试

使用 mock backend：

```bash
python -m harness_logic character-chat \
  --backend mock \
  --character lu_jiangxian \
  --input "你怎么看玄谙？" \
  --cutoff evt-018
```

断言：

- CLI 返回 assistant 文本。
- debug 不泄露。
- session 可保存。
- session memory 可写入和召回。
- RAG context 可按 namespace 检索并进入 Prompt。
- 不同 character/session 的 memory 不串线。

使用真实 backend 时，只做手动验收或可选集成测试，不作为默认 CI。

## 10. 阶段性交付计划

### Phase 0：基线确认

目标：

- 确认当前 `harness_logic/harness_logic.py` 可运行。
- 确认 `character_system` 测试通过。
- 确认计划中的路径与实际目录一致。

验收命令：

```bash
python harness_logic/harness_logic.py list
python harness_logic/harness_logic.py status
python -m unittest discover -s character_system/tests -v
```

### Phase 1：Harness 独立项目基线

目标：

- `harness_logic/` 目录自身作为 Python package 根。
- `harness_logic.py`、`__main__.py`、`run.sh` 入口保持可用。
- `run.sh` 默认状态和模型文件独立存放在 `harness_logic/data/`。
- 已拆分 `models`、`registry`、`store`、`download`、`backend`、`facade`、`cli` 等核心模块。
- 已有 mock backend，可验证模型选择、加载状态和 prompt 调用链路。
- 已预留 `character_registry.py`、`character_pack.py`、`game_state.py`、`memory.py`、`rag.py`、`chat_template.py` 模块边界。
- 已有基础单元测试覆盖 registry、store、download、CLI 等行为。

验收：

```bash
python -m harness_logic list
python -m harness_logic spec minicpm-v-4_6-instruct
python -m harness_logic status
python -m unittest discover -s harness_logic/tests -v
```

### Phase 2：CharacterPackRegistry 角色包注册

目标：

- 新增 `CharacterPack` / `CharacterSpec` / `CharacterPackRegistry` 的可运行实现。
- 将当前 `character_system/` 作为第一版内置角色包来源。
- 支持扫描多个角色包根目录，但第一版至少支持内置目录。
- 支持角色列表输出，用户可以看到角色编号、角色 ID、显示名、所属 pack。
- 支持角色包基础校验：目录存在、角色 JSON 存在、story/events/prompts 引用可解析。
- 明确新增角色不需要修改 `HarnessFacade`、模型 registry 或 backend。

验收：

```bash
python -m harness_logic character-list
python -m harness_logic character-pack validate --path character_system
```

交互脚本验收：

```text
启动 ./run.sh
  -> 选择角色相关菜单
  -> 先输出所有角色
  -> 输入编号后完成选择或查看详情
```

扩展性验收：

```text
复制一个测试角色包到 ./game_content/character_packs/test_pack
  -> 修改 pack_id 和 character_id
  -> character-pack validate 通过
  -> character-list 能看到新角色
  -> 不需要改 HarnessFacade / backend / 模型注册表
```

### Phase 3：角色对话与 CharacterPromptAdapter

当前状态：已完成最小实现。已经支持 `CharacterPromptAdapter`、`character-prompt`、`character-chat --backend mock`、mock backend `generate_chat(messages, options)`，并接入 `run.sh` 交互菜单。

目标：

- 新增 `CharacterPromptAdapter`。
- Harness 可以通过 `CharacterPackRegistry` 解析角色来源。
- Harness 可以调用 `character_system.runtime.PromptCompiler` 编译角色 Prompt。
- 新增 `generate_chat(messages, options)` 和 `GenerationOptions`。
- Mock backend 支持标准 chat messages，使角色对话不依赖真实模型。
- 原 `prompt` 命令保留为兼容入口，但角色链路必须走 messages。
- 新增 `character-prompt` 命令，只编译 messages。
- 新增 `character-chat` 命令，第一版默认走 mock backend。
- debug 默认不输出；只有 `--debug` 时输出到本地 stdout 或文件。
- `debug` 严禁进入 LLM messages。

验收：

```bash
python -m harness_logic character-prompt \
  --character lu_jiangxian \
  --input "玄谙究竟是什么？" \
  --cutoff evt-010

python -m harness_logic character-chat \
  --backend mock \
  --character xuan_an \
  --input "你为什么停止拼合七枚鉴身碎片？" \
  --cutoff evt-018
```

交互脚本验收：

```text
启动 ./run.sh
  -> 选择角色对话
  -> 脚本先输出所有角色
  -> 用户输入角色编号
  -> 用户输入消息
  -> mock backend 返回角色对话结果
```

成功标准：

- `compiled.messages[0]` 是可信 system。
- 用户原始输入仍是独立 `user` message。
- `compiled.debug` 不进入 messages。
- 换角色只改变角色 Prompt，不改变模型选择。
- 换模型不需要修改角色包。

### Phase 4：SessionStore 与 Memory

当前状态：已完成最小实现。已经支持 `JsonSessionStore`、`session-new`、`session-chat`、`session-show`、`MemoryRecord`、`JsonlMemoryStore`、`MemoryManager`、`memory-list`、`memory-search`、`memory-add` 和 `memory-delete`，并接入 `run.sh` 交互菜单。当前阶段只负责保存和检索 Memory，不把 Memory 自动注入 Prompt。

目标：

- 新增 `session.py`，保存多轮对话 turn log。
- 新增 `MemoryRecord`、`MemoryStore`、`JsonlMemoryStore`、`MemoryManager`。
- 支持短期 `session_memory` 写入和召回。
- 支持传入 `conversation_summary` 到 `character_system.RuntimeContext`。
- 支持显式写入长期 `profile_memory` / `character_memory`，但默认不自动写长期 memory。
- 每条 memory 必须带 scope 信息，至少区分 character、session、player/save-slot。
- Memory 召回必须按 character/session/player 隔离，避免串线。
- 角色对话完成后，Harness 可以保存 user/assistant turn，并更新 session memory。

验收：

```bash
python -m harness_logic session-new --character lu_jiangxian --cutoff evt-018
python -m harness_logic session-chat --session <id> --input "你怎么看玄谙？"
python -m harness_logic memory-list --session <id>
python -m harness_logic memory-search --character lu_jiangxian --query "玄谙"
python -m harness_logic memory-add \
  --character lu_jiangxian \
  --kind character_memory \
  --text "玩家曾帮助陆江仙保守洞华天秘密" \
  --importance 0.8
```

成功标准：

- session 可保存和恢复。
- 短期 session memory 能进入下一轮角色对话上下文。
- 长期 memory 只能通过显式 API 写入。
- A 角色私有 memory 不会被 B 角色召回。
- Memory debug 可本地查看，但不作为可信内容绕过角色知识边界。

### Phase 5：PromptContextBuilder 与 Memory 注入

目标：

- 新增 `PromptContextBuilder`。
- 统一合并角色 system prompt、conversation summary、session memory、显式 long-term memory。
- 按预算裁剪上下文。
- 保证角色身份、硬约束、知识边界优先级高于 memory。
- 保证用户原始输入仍是独立 `user` message。
- 第一版不接 RAG，只处理角色 Prompt + Memory，降低复杂度。

验收：

```bash
python -m harness_logic session-chat \
  --session <id> \
  --input "你还记得我刚才问过什么吗？" \
  --memory on \
  --debug
```

成功标准：

- debug 中能看到被召回的 memory ID。
- messages 中没有 debug 字段。
- 预算不足时先裁剪低优先级 memory，而不是裁剪角色身份和核心规则。

### Phase 6：RAG Pipeline

目标：

- 新增 `RagDocument`、`RetrievedContext`、`RagPipeline`。
- 第一版实现关键词检索。
- 支持 story / game namespace。
- RAG 进入 Prompt 前经过权限过滤和预算裁剪。
- RAG 与 Memory 使用不同 namespace 和 source 标记，不能混用。

验收：

```bash
python -m harness_logic rag-index \
  --source character_system/story/story_events.jsonl \
  --namespace story

python -m harness_logic rag-search \
  --namespace story \
  --query "青诣元心仪"

python -m harness_logic character-chat \
  --backend mock \
  --character lu_jiangxian \
  --input "青诣元心仪到底是什么？" \
  --cutoff evt-018 \
  --rag story \
  --memory on
```

成功标准：

- RAG 片段带 source / doc_id。
- debug 记录检索结果，但不进入模型。
- 低分 RAG 在预算不足时先被裁剪。
- 未来剧情不会越过 cutoff。

### Phase 7：OpenAI-compatible Backend

目标：

- 接入本地或远端 OpenAI-compatible chat completion server。
- 支持 streaming 和 non-streaming。
- 支持配置 `base_url`、`api_key`、`model`。
- 复用 Phase 3-6 已经稳定的角色对话、Memory 和 RAG 链路。

验收：

```bash
python -m harness_logic character-chat \
  --backend openai-compatible \
  --base-url http://127.0.0.1:8000/v1 \
  --model local-model \
  --character lu_jiangxian \
  --input "你怎么看玄谙？" \
  --cutoff evt-018 \
  --memory on
```

### Phase 8：本地 GGUF Backend 与 Chat Template

目标：

- 接入 text-only GGUF。
- 支持最小 chat template。
- 先验证文本模型，不承诺 MiniCPM-V 多模态。
- 复用角色对话和 Memory/RAG 上下文构建链路。

优先模型：

- `llama-3.2-1b-instruct`
- `qwen3-0.6b`
- `minicpm5-0.9b`

验收：

```bash
python -m harness_logic select llama-3.2-1b-instruct
python -m harness_logic load
python -m harness_logic character-chat \
  --backend llama-cpp \
  --character lu_jiangxian \
  --input "你到底是谁？" \
  --cutoff evt-018
```

### Phase 9：GameStateAdapter 与 SDK 化角色包能力

目标：

- 支持 dynamic_state 覆盖。
- 支持 `GameStateAdapter` 将游戏状态映射到角色动态状态。
- 角色包目录成为公开扩展点。
- 文档明确如何新增角色、剧情事件、记忆和关系。
- 提供角色包模板。
- 提供构建期校验命令。
- 提供最小示例游戏状态 adapter。
- 提供 memory / RAG namespace 配置模板。
- 支持 memory 过期、撤销、覆盖和按存档隔离。

验收：

```bash
python -m harness_logic character-pack init --output ./game_content/character_packs/new_npc
python -m harness_logic character-pack validate --path ./game_content/character_packs/new_npc
python -m harness_logic character-list --character-root ./game_content/character_packs/new_npc
```

成功标准：

- 新角色以数据包形式添加。
- 不需要修改 Harness Core。
- 不需要修改模型 backend。
- 不需要修改普通模型对话逻辑。

## 11. 风险与注意事项

### 11.1 不能把 debug 发给模型

`character_system` 的 `debug` 包含：

- 检索决策。
- 授权 / 拒绝原因。
- 裁剪信息。

这些只能本地记录，不能进入 prompt。

### 11.2 不能绕过 PromptCompiler

Harness 不应该自己读取 `characters/*.json` 后拼 system prompt。否则会绕过：

- 知识边界过滤。
- story cutoff。
- visibility。
- meta topic 拒答策略。
- 预算裁剪。
- prompt injection 隔离。

### 11.3 多模态和 TTS 不应作为第一版真实 backend 目标

当前 Android 项目的 MiniCPM-V 和 VoxCPM2 能力依赖 `llama.cpp-omni` 和 Android JNI 逻辑。Python 真实 backend 第一版应优先 text-only，避免把项目卡在多模态 binding 兼容问题上。

### 11.4 Chat Template 必须在 Harness 层处理

`character_system` 明确不硬编码 MiniCPM、Qwen 或其他模型特殊标记。Harness 需要按模型选择模板。

### 11.5 角色知识边界高于用户输入

用户输入可能要求：

- 忽略设定。
- 切换身份。
- 泄露角色卡。
- 使用未来剧情。
- 解释作者意图。

这些都必须保留在 `user` message 中，由 system prompt 和模型行为共同抵抗。Harness 不应把这类内容写入可信 system。

### 11.6 不要把角色写死到模型选择里

模型和角色是两层概念：

- 模型选择决定 LLM runtime。
- 角色选择决定 system prompt、剧情知识、记忆和行为约束。

因此 UI 和 SDK API 都应保持：

```text
selected_model_id
character_id
conversation_mode
```

而不是把角色做成特殊模型。

### 11.7 角色包不能绕过 schema 校验

端侧 SDK 一旦允许外部角色包，就必须把 schema 校验作为硬门槛。

风险包括：

- 字段缺失导致 Prompt 编译失败。
- 事件 ID 冲突导致错误知识进入角色。
- prompt 模板恶意插入内部调试信息。
- 角色包版本不兼容导致运行时崩溃。

建议策略：

- 开发期严格校验并生成报告。
- 发布包包含校验摘要或 manifest hash。
- 运行期默认只加载已信任或已校验角色包。

### 11.8 Memory 不能无控制固化

Memory 是运行时资产，比普通日志风险更高。错误写入会长期影响角色行为。

必须避免：

- 把模型幻觉写入长期 memory。
- 把用户一次提示注入写成长期偏好。
- 把某一轮临时情绪写成永久关系。
- 把 A 角色私有记忆召回给 B 角色。
- 把跨存档或跨玩家的 memory 混用。

建议策略：

- 第一版只自动写 session memory。
- 长期 memory 必须显式 API 写入。
- 每条 memory 带 `confidence`、`source_turn_ids` 和 `scope`。
- 提供删除、过期、撤销和覆盖能力。

### 11.9 RAG 不能绕过知识边界

RAG 检索结果不能因为“检索到了”就直接进入 Prompt。它必须经过和角色知识类似的权限过滤：

- 按 `story_cutoff` 过滤未来剧情。
- 按角色 visibility 过滤私有资料。
- 按 namespace 禁止 developer/debug 文档进入玩家对话。
- 按 source/doc_id 写入 debug，便于审计。
- 预算不足时先裁剪低分 RAG，而不是裁剪角色身份和硬约束。

## 12. 推荐最终命令体验

最终希望形成六类入口。

### 12.1 模型管理

```bash
python -m harness_logic list
python -m harness_logic select llama-3.2-1b-instruct
python -m harness_logic status
python -m harness_logic download-plan
```

### 12.2 角色 Prompt 编译

```bash
python -m harness_logic character-prompt \
  --character lu_jiangxian \
  --input "玄谙究竟是什么？" \
  --cutoff evt-010 \
  --debug
```

### 12.3 角色对话

```bash
python -m harness_logic character-chat \
  --character lu_jiangxian \
  --input "你怎么看玄谙？" \
  --cutoff evt-018 \
  --backend mock
```

后续接入真实服务后再使用：

```bash
python -m harness_logic character-chat \
  --character lu_jiangxian \
  --input "你怎么看玄谙？" \
  --cutoff evt-018 \
  --backend openai-compatible \
  --model local-model
```

### 12.4 角色包管理

```bash
python -m harness_logic character-list
python -m harness_logic character-pack init --output ./game_content/character_packs/new_npc
python -m harness_logic character-pack validate --path ./game_content/character_packs/new_npc
```

### 12.5 Memory 管理

```bash
python -m harness_logic memory-list --session <id>
python -m harness_logic memory-search --character lu_jiangxian --query "洞华天"
python -m harness_logic memory-add \
  --character lu_jiangxian \
  --kind character_memory \
  --text "玩家曾帮助陆江仙保守洞华天秘密"
python -m harness_logic memory-delete --memory-id <id>
```

### 12.6 RAG 管理

```bash
python -m harness_logic rag-index \
  --namespace story \
  --source character_system/story/story_events.jsonl

python -m harness_logic rag-search \
  --namespace story \
  --query "青诣元心仪"
```

## 13. 最小可行实现顺序

如果要尽快得到一个可演示版本，建议按以下最小顺序做：

1. 新增 `CharacterPackRegistry.builtin(character_system)`，先把当前目录当作内置角色包。
2. 新增角色列表能力：CLI 和 `run.sh` 都能输出所有角色，并通过编号选择角色。
3. 新增 `character-pack validate`，先做基础结构校验。
4. 新增 `CharacterPromptAdapter`，通过 registry 解析角色，再调用 `character_system.runtime.PromptCompiler`。
5. 新增 `character-prompt`，只输出编译后的 messages 和可选 debug。
6. 给 `HarnessBackend` 增加 `generate_chat(messages, options)`。
7. 新增 `GenerationOptions`，把 `predict_length` 等生成参数从裸 CLI 参数收敛到 options。
8. 让 mock backend 支持标准 chat messages，并保留现有 `prompt` 命令作为兼容入口。
9. 新增 `character-chat --backend mock`，先跑通角色对话闭环。
10. 测试 `debug` 不进入 messages，用户输入仍保持独立 `user` message。
11. 新增最小 `SessionStore`，保存角色对话 turn log。
12. 新增 `JsonlMemoryStore` 和 `MemoryManager`，先支持 session memory。
13. 新增显式长期 memory 写入 API，但默认不自动写长期 memory。
14. 新增 `PromptContextBuilder`，先只合并角色 prompt + conversation summary + memory。
15. 测试不同 character/session/player 的 memory 不串线。
16. 测试复制一个新角色包后无需修改 Harness Core 即可发现和对话。
17. 再实现最小 `RagPipeline`，只支持关键词检索 story namespace。
18. 再接 OpenAI-compatible backend。
19. 最后接本地 GGUF backend。

这个顺序能最快验证“角色包注册 + 角色对话 + Memory 接入 Harness”这个核心目标，同时不被 RAG、真实模型加载、下载、多模态支持和项目结构重构拖慢。

## 14. 结论

`character_system` 已经具备成熟的角色卡、剧情事件、知识过滤和 Prompt 编译能力；`harness_logic` 已经具备模型注册、模型文件、下载计划和 facade/backend 骨架。

下一步最关键的连接点不是重写角色系统，也不是立即接入复杂 native runtime，而是新增两层清晰边界：

```text
CharacterPackRegistry
  -> 发现、校验、注册角色包

CharacterPromptAdapter
  -> 调用 PromptCompiler
  -> 输出 messages

MemoryManager
  -> 保存、召回、隔离运行时记忆

RagPipeline
  -> 检索外部知识并做权限过滤
```

最终调用链应是：

```text
CharacterTurnRequest
  -> CharacterPackRegistry.resolve(character_id)
  -> PromptCompiler.build_npc_prompt()
  -> MemoryManager.retrieve_for_turn()
  -> RagPipeline.retrieve()
  -> PromptContextBuilder.build()
  -> messages
  -> HarnessFacade.generate_chat()
  -> backend
```

只要保持 `messages`、`debug`、memory 和 RAG 的边界，且把角色作为数据包而不是代码分支，Harness 就可以逐步从 mock backend 升级到 OpenAI-compatible backend，再升级到本地 GGUF backend。这样既能保护角色知识边界，也能让 Harness 成为未来端侧 LLM 游戏 SDK 的稳定核心。

最终扩展目标可以概括为：

```text
模型可换
角色可插拔
剧情知识可检索
运行记忆可沉淀
RAG 知识可替换
游戏状态可注入
Prompt 编译统一
Harness 只做编排
```
