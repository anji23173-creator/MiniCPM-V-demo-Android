# Harness Logic

`harness_logic` 是从原 Android 项目中提取出来的 Python 版 Harness 编排项目。它的目标是把 Android 工程里已有的模型注册、模型文件管理、下载源规划、backend facade 等逻辑整理成一个独立、可运行、可测试的 Python 项目。

当前已经完成 **Phase 1：项目化拆分**、**Phase 2：角色包注册**、**Phase 3：角色对话接入** 和 **Phase 4：SessionStore 与 Memory**。项目已经可以作为独立 Python 子项目运行，能发现、列出和校验内置 `character_system` 角色包，也能用 mock backend 跑通角色 Prompt 编译、角色对话、会话保存和 Memory 写入/搜索链路。真实 LLM 推理和 RAG 还未实现。

## 项目定位

当前项目已经实现：

- 模型元数据定义。
- `ModelInfo -> HarnessModelSpec` 转换。
- 模型注册表 `HarnessModelRegistry`。
- 选中模型状态保存。
- 本地模型 artifact 路径推导。
- 模型文件完整性检查。
- 旧模型目录迁移逻辑。
- HuggingFace / ModelScope / Direct 下载计划生成。
- mock backend。
- `HarnessFacade` 统一入口。
- CLI 命令。
- 内置 `character_system` 角色包注册。
- 角色列表输出。
- 角色包基础校验。
- 角色 Prompt 编译。
- mock 角色对话。
- 角色会话创建、查看和 turn log 保存。
- JSONL Memory 写入、列表、搜索和删除。
- 基础单元测试。

当前项目还没有实现：

- 真实 GGUF 下载。
- 真实 LLM 推理。
- llama.cpp / llama-cpp-python backend。
- OpenAI-compatible backend。
- RAG。
- 游戏状态适配。

这些能力的设计见：

[HARNESS_LLM_CHARACTER_INTEGRATION_PLAN.md](HARNESS_LLM_CHARACTER_INTEGRATION_PLAN.md)

## 目录结构

```text
harness_logic/
├── README.md
├── pyproject.toml
├── run.sh
├── harness_logic.py
├── __init__.py
├── __main__.py
├── constants.py
├── models.py
├── registry.py
├── store.py
├── download.py
├── backend.py
├── facade.py
├── cli.py
├── utils.py
├── backends/
│   ├── __init__.py
│   └── mock_backend.py
├── tests/
│   ├── test_cli.py
│   ├── test_character_adapter.py
│   ├── test_character_registry.py
│   ├── test_download.py
│   ├── test_registry.py
│   └── test_store.py
├── character_system/
├── data/
├── character_adapter.py
├── character_pack.py
├── character_registry.py
├── chat_template.py
├── game_state.py
├── session.py
├── memory.py
└── rag.py
```

核心文件说明：

| 文件 | 作用 |
| --- | --- |
| `models.py` | Harness 数据结构和枚举，例如 `ModelInfo`、`HarnessModelSpec`、`LlamaState`。 |
| `registry.py` | 当前内置模型列表、模型 family/capability 推导、`HarnessModelRegistry`。 |
| `store.py` | 选中模型状态、本地 artifact 路径、完整性检查、旧目录迁移。 |
| `download.py` | 下载计划生成，当前只输出 URL，不执行下载。 |
| `backend.py` | mock backend 基类，模拟模型加载和生成状态。 |
| `backends/mock_backend.py` | 当前可运行的 mock backend / `LlamaBackendAdapter` 兼容层。 |
| `facade.py` | `HarnessFacade`，对外统一封装 registry、store、download、backend。 |
| `cli.py` | 命令行入口实现。 |
| `run.sh` | 推荐使用的 Bash 交互式运行入口，启动后通过菜单执行 Harness 操作。 |
| `harness_logic.py` | 兼容旧脚本入口，内部转发到 `cli.py`。 |
| `__main__.py` | 支持 `python -m harness_logic ...`。 |
| `character_adapter.py` | 调用 `character_system.runtime.PromptCompiler`，把角色请求编译成标准 chat messages。 |
| `character_pack.py` | 角色包、角色元数据和角色包校验结果的数据结构。 |
| `character_registry.py` | 角色包发现、内置 `character_system` 注册、角色列表和基础校验。 |
| `chat_template.py` | Phase 2+ 预留：模型 chat template。 |
| `game_state.py` | Phase 2+ 预留：游戏状态适配。 |
| `session.py` | 角色会话文件、turn log、conversation summary 和动态状态存储。 |
| `memory.py` | 运行时 Memory 数据结构、JSONL 存储、写入、列表、搜索和删除。 |
| `rag.py` | Phase 2+ 预留：RAG 编排。 |

## 如何运行

以下命令建议从仓库根目录运行：

```bash
cd <repo-root>
```

推荐使用 `run.sh`。进入 `harness_logic/` 目录后启动脚本：

```bash
cd harness_logic
./run.sh
```

也可以从仓库根目录直接启动：

```bash
./harness_logic/run.sh
```

启动后脚本会显示交互式菜单：

```text
1. 列出当前注册模型
2. 查看当前选中模型状态
3. 查看某个模型的完整 spec
4. 选择模型
5. 查看当前选中模型的下载计划
6. 初始化 mock demo 文件
7. 发送一条 mock 对话消息
8. 自动运行完整 mock demo
15. 列出当前注册角色
16. 通过编号选择角色并查看信息
17. 校验内置角色包
18. 编译角色 Prompt
19. 运行 mock 角色对话
20. 新建角色会话
21. 在会话中运行 mock 角色对话
22. 查看角色会话
23. 列出 Memory
24. 新增 Memory
25. 搜索 Memory
...
```

输入菜单编号后执行对应操作。执行完成后会回到菜单。输入 `q`、`quit`、`exit` 或按 `Ctrl+C` 可以退出。

当操作需要选择模型时，脚本会先输出当前所有可用模型，并给每个模型分配编号。用户只需要输入编号，不需要手动输入完整的 `model_id`。

当操作需要选择角色时，脚本会先输出当前所有可用角色，并给每个角色分配编号。用户只需要输入编号，不需要手动输入完整的 `character_id`。

`run.sh` 默认把状态和模型文件放到 `harness_logic` 项目自己的运行目录：

```text
harness_logic/data/
```

可以通过环境变量改成其他目录：

```bash
HARNESS_ROOT=./runtime/harness-root ./harness_logic/run.sh
```

底层 Python CLI 仍然可用：

```bash
python3 harness_logic/harness_logic.py list
```

## Mock 对话流程

当前没有真实 LLM backend。`prompt` 命令使用 mock backend，只验证 Harness 调用链路。

启动脚本后，选择：

```text
8. 自动运行完整 mock demo
```

脚本会先输出模型列表，用户输入编号选择 demo 模型，然后脚本会创建占位模型文件，并发送一条 mock 对话消息。

`touch-demo-files` 会创建极小的占位 artifact 文件，只用于让 mock backend 的 `load` 和 `prompt` 流程跑通。它不是真实模型文件，不能用于真实推理。

## 角色对话流程

当前角色对话已经接入到 mock backend。它会真实调用 `character_system` 的 Prompt 编译逻辑，但不会调用真实大模型。

编译角色 Prompt：

```bash
python3 -m harness_logic character-prompt \
  --character lu_jiangxian \
  --input "玄谙究竟是什么？" \
  --cutoff evt-010
```

运行 mock 角色对话：

```bash
python3 -m harness_logic character-chat \
  --backend mock \
  --model llama-3.2-1b-instruct \
  --character xuan_an \
  --input "你为什么停止拼合七枚鉴身碎片？" \
  --cutoff evt-018 \
  --touch-demo-files
```

通过交互脚本使用：

```text
启动 ./run.sh 后选择菜单中的 18 或 19
```

注意：`character-prompt` 输出的是标准 `messages`；`debug` 默认不会输出，也不会进入模型消息。需要本地调试时可以加 `--debug`。

## Session 与 Memory

创建角色会话：

```bash
python3 -m harness_logic session-new \
  --character lu_jiangxian \
  --cutoff evt-018 \
  --model llama-3.2-1b-instruct
```

在会话中运行一轮 mock 角色对话：

```bash
python3 -m harness_logic session-chat \
  --session <session_id> \
  --input "你怎么看玄谙？" \
  --touch-demo-files
```

查看会话：

```bash
python3 -m harness_logic session-show --session <session_id>
```

列出或搜索 Memory：

```bash
python3 -m harness_logic memory-list --session <session_id>
python3 -m harness_logic memory-search --character lu_jiangxian --query "洞华天"
```

显式新增长期角色 Memory：

```bash
python3 -m harness_logic memory-add \
  --character lu_jiangxian \
  --kind character_memory \
  --text "玩家曾帮助陆江仙保守洞华天秘密"
```

当前 Phase 4 只负责保存和检索 Memory；Memory 还不会自动注入角色 Prompt。Memory 注入属于 Phase 5。

## 状态和模型文件位置

默认情况下，底层 Python CLI 会在 `harness_logic/data/` 下保存自己的状态和模型文件：

```text
harness_logic/data/.harness_state.json
harness_logic/data/models/<model_id>/<artifact_file>
```

这是 `harness_logic` 独立于 Android App 的本地运行目录，不复用仓库根目录的 `models/`。如果需要临时切换位置，可以传 `--root` 或设置 `HARNESS_ROOT`。

示例：

```text
harness_logic/data/models/llama-3.2-1b-instruct/Llama-3.2-1B-Instruct-Q4_K_M.gguf
harness_logic/data/models/minicpm-v-4/mmproj-model-f16.gguf
```

## 当前注册模型

当前内置模型来自 Android 项目的模型清单：

- `minicpm-v-4`
- `minicpm-v-4_6-instruct`
- `minicpm5-0.9b`
- `voxcpm2`
- `llama-3.2-1b-instruct`
- `qwen3-0.6b`

这些模型的下载源、artifact 和 capability 可以通过以下命令查看：

启动 `./run.sh` 后选择菜单中的 `1`、`3`、`5`。

## 当前注册角色

当前内置角色来自：

```text
harness_logic/character_system/
```

已注册角色：

- `lu_jiangxian`：陆江仙
- `xuan_an`：玄谙

通过交互脚本查看：

```text
启动 ./run.sh 后选择菜单中的 15
```

通过底层 CLI 查看：

```bash
python3 -m harness_logic character-list
```

校验内置角色包：

```text
启动 ./run.sh 后选择菜单中的 17
```

或使用 CLI：

```bash
python3 -m harness_logic character-pack validate
```

## 开发和测试

运行单元测试：

启动 `./run.sh` 后选择菜单中的 `12`。

运行语法检查：

启动 `./run.sh` 后选择菜单中的 `13`。

当前测试覆盖：

- CLI `list` 命令。
- 模型 spec 生成。
- MiniCPM-V 4.6 capability 和 artifact。
- 模型选择与 artifact 路径。
- 文本模型 artifact 完整性判断。
- 默认模型 HuggingFace / ModelScope 下载计划。
- 内置角色包发现和校验。
- 角色 Prompt 编译。
- mock 角色对话。
- 角色 session 保存。
- session memory 自动写入。
- 显式 memory 写入与搜索。

## 作为 Python 模块使用

示例：

```python
from pathlib import Path

from harness_logic import CharacterPackRegistry, CharacterTurnRequest, HarnessFacade, HarnessModelRegistry

facade = HarnessFacade(Path("harness_logic/data"))

for spec in HarnessModelRegistry.available_specs():
    print(spec.id, spec.display_name)

facade.set_selected_model("llama-3.2-1b-instruct")
print(facade.get_selected_model_spec())

character_registry = CharacterPackRegistry.default()
for character in character_registry.available_characters():
    print(character.character_id, character.display_name)

turn = facade.compile_character_turn(
    CharacterTurnRequest(
        character_id="lu_jiangxian",
        user_input="玄谙究竟是什么？",
        story_cutoff="evt-010",
    )
)
print(turn.messages)

session = facade.create_character_session(
    character_id="lu_jiangxian",
    story_cutoff="evt-018",
    selected_model_id="llama-3.2-1b-instruct",
)
print(session.session_id)
```

## 后续阶段

后续计划包括：

- Phase 5：PromptContextBuilder 与 Memory 注入。
- Phase 6：RAG Pipeline。
- Phase 7：OpenAI-compatible backend。
- Phase 8：本地 GGUF backend 与 Chat Template。
- Phase 9：GameStateAdapter 与 SDK 化角色包能力。

详细路线见：

[HARNESS_LLM_CHARACTER_INTEGRATION_PLAN.md](HARNESS_LLM_CHARACTER_INTEGRATION_PLAN.md)

## 注意事项

- 当前 `download-plan` 只展示下载 URL，不会下载文件。
- 当前 `prompt` 和 `character-chat --backend mock` 只走 mock backend，不是真实推理。
- `touch-demo-files` 创建的是占位文件，不是真实模型。
- `memory.py`、`rag.py` 等文件当前是预留模块。
- 默认运行数据目录是 `harness_logic/data/`；该目录下的状态文件、占位文件和真实模型文件不会提交到 Git。
