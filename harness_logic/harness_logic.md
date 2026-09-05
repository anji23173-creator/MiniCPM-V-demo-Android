# harness_logic.py 逻辑与功能分析

`harness_logic.py` 是从当前 Android 项目中提取出来的一个独立 Python 版本 Harness 逻辑脚本。它的目标不是替代 Android App，也不是直接运行 JNI/native 推理，而是把项目中已经形成的 Harness 编排层转换成一个可以在命令行运行、检查和演示的数据与流程模型。

原 Android 项目的主链路可以简化为：

```text
Activity
  -> HarnessFacade
      -> LlamaModelStore
      -> LlamaDownloadManager
      -> LlamaBackendAdapter
          -> LlamaEngine
              -> JNI / llama.cpp-omni
```

Python 脚本保留了前半部分：

```text
CLI command
  -> HarnessFacade
      -> LlamaModelStore
      -> LlamaDownloadManager
      -> LlamaBackendAdapter
          -> HarnessBackend mock runtime
```

因此，它适合用来分析模型注册、artifact 组织、下载源生成、模型选择状态、文件完整性检查、旧文件迁移和 facade/backend 调用关系。

## 1. 脚本定位

脚本开头的 docstring 已经明确说明它是 Android Harness 层的 standalone extraction。这里的 “standalone” 主要有三个含义：

1. 不依赖 Android `Context`、`SharedPreferences`、`LlamaEngine`、JNI 或 native 动态库。
2. 不默认下载真实 GGUF 模型文件，避免命令行执行时直接触发大文件下载。
3. 提供一个 mock backend，使 `load`、`prompt` 这类流程可以在普通 Python 环境里跑通。

这也意味着它不是一个真实推理脚本。它不会调用 `llama.cpp-omni`，也不会产生真实模型输出。它复刻的是项目的 Harness 编排逻辑，而不是 native 推理能力。

## 2. 常量与运行状态

脚本定义了几个和 Android `LlamaEngine` 对齐的常量：

```python
DEFAULT_PREDICT_LENGTH = 1024
MODEL_SUBDIR = "models"
MIN_IMAGE_SLICE = 1
MAX_IMAGE_SLICE = 9
DEFAULT_IMAGE_SLICE = MAX_IMAGE_SLICE
```

这些值对应 Android 侧的默认生成长度、模型目录名和图片切片数量范围。

`LlamaState` 用 `Enum` 模拟 Android 里的 sealed class 状态，包括：

- `Initialized`
- `LoadingModel`
- `ModelReady`
- `PrefillingImage`
- `Generating`
- `UnloadingModel`
- `Error`

这些状态让 Python mock backend 可以模拟加载、卸载、生成和错误流转。

## 3. Harness 数据模型

脚本用 `dataclass` 定义了 Harness 的核心结构。

### 3.1 ModelInfo

`ModelInfo` 对应 Android 项目里的 `ModelInfo.kt`。它仍然是当前模型清单的基础事实来源，包含：

- 模型 id
- 展示名称
- GGUF 文件名
- mmproj 视觉 projector 文件名
- acoustic TTS 文件名
- HuggingFace / ModelScope repo
- 分支名
- direct URL
- MD5

它还实现了几个属性方法：

- `is_text_only`：没有 mmproj，也没有 acoustic，即文本模型。
- `is_tts`：存在 acoustic 文件，即 TTS 模型。
- `gguf_remote_path`：远端 GGUF 路径，优先使用 remote name，否则回退到本地文件名。
- `mmproj_remote_path`：视觉 projector 的远端路径。
- `acoustic_remote_path`：TTS acoustic artifact 的远端路径。
- `has_direct_urls`：是否配置了 direct 下载 URL。
- `has_hf_ms_sources`：是否同时配置了 HF 和 MS 源。

这部分逻辑对应 Android 侧 `ModelInfo` 的派生属性。

### 3.2 HarnessArtifact

`HarnessArtifact` 描述一个模型所需的文件 artifact：

```python
HarnessArtifact(
    id="llm",
    file_name="MiniCPM-V-4_6-Q4_K_M.gguf",
    required=True,
    remote_path="MiniCPM-V-4_6-Q4_K_M.gguf",
    md5="..."
)
```

当前脚本中主要有三类 artifact：

- `llm`：主 GGUF 模型。
- `vision_projector`：视觉模型需要的 mmproj 文件。
- `acoustic`：TTS 模型需要的 acoustic GGUF 文件。

`required=True` 表示该文件必须存在，模型才算下载完整。

### 3.3 HarnessDownloadSource

`HarnessDownloadSource` 描述 artifact 的下载来源。支持三种类型：

- `HUGGING_FACE`
- `MODELSCOPE`
- `DIRECT`

HF / ModelScope 类型保存 repo、branch、remote path；Direct 类型保存完整 URL。

脚本没有真正执行下载，而是通过这些结构生成下载计划。

### 3.4 HarnessRuntimeHints

`HarnessRuntimeHints` 保存模型运行建议：

- 默认生成长度
- 推荐线程数
- 默认图片切片数
- context size
- 是否支持 system prompt

例如 `minicpm-v-4_6-instruct` 的 `context_size` 是 `8192`，视觉模型默认图片切片数是 `9`。

### 3.5 HarnessModelSpec

`HarnessModelSpec` 是 Harness 层真正希望暴露的通用模型定义。它由 `ModelInfo` 转换而来，包含：

- `id`
- `display_name`
- `family`
- `capabilities`
- `artifacts`
- `download_sources`
- `runtime_hints`

这对应 Android 项目中阶段三引入的通用 spec 层。

## 4. 模型清单

`AVAILABLE_MODELS` 是从 Android `ModelInfo.AVAILABLE_MODELS` 翻译过来的模型清单。当前包含：

| id | 类型 | artifact |
| --- | --- | --- |
| `minicpm-v-4` | 视觉模型 | `llm` + `vision_projector` |
| `minicpm-v-4_6-instruct` | 视觉 + 视频模型 | `llm` + `vision_projector` |
| `minicpm5-0.9b` | 文本模型 | `llm` |
| `voxcpm2` | TTS 模型 | `llm` + `acoustic` |
| `llama-3.2-1b-instruct` | 文本模型 | `llm` |
| `qwen3-0.6b` | 文本模型 | `llm` |

这个清单仍然体现了当前项目的现实状态：`ModelInfo` 还是底层模型信息来源，`HarnessModelRegistry` 是它上方的一层映射和统一入口。

## 5. ModelInfo 到 HarnessModelSpec 的转换

核心转换函数是：

```python
model_to_harness_spec(model: ModelInfo) -> HarnessModelSpec
```

它做四件事。

第一，推导能力：

- 所有模型默认有 `TEXT`。
- 如果有 `mmproj_file_name`，增加 `VISION`。
- 如果模型 id 是 `minicpm-v-4_6-instruct`，额外增加 `VIDEO`。
- 如果有 `acoustic_file_name`，增加 `TTS`。

第二，生成 artifact：

- 所有模型都有 `llm` artifact。
- 视觉模型增加 `vision_projector` artifact。
- TTS 模型增加 `acoustic` artifact。

第三，生成下载源：

- 如果配置了 `hf_repo`，生成 HuggingFace source。
- 如果配置了 `ms_repo`，生成 ModelScope source。
- 如果配置了 direct URL，生成 Direct source。

第四，推导 runtime hints：

- MiniCPM-V 4.6：`context_size=8192`，图片切片默认 `9`。
- 其他视觉模型：`context_size=4096`，图片切片默认 `9`。
- 文本模型：`context_size=4096`。

## 6. HarnessModelRegistry

`HarnessModelRegistry` 是模型注册表。

它在类加载时执行：

```python
entries = [
    HarnessModelEntry(model, model_to_harness_spec(model))
    for model in AVAILABLE_MODELS
]
```

也就是说，它把每个 legacy `ModelInfo` 包装成：

```text
HarnessModelEntry
  - legacy_model_info
  - spec
```

它暴露的方法包括：

- `available_entries()`
- `available_model_infos()`
- `available_specs()`
- `find_entry(model_id)`
- `find_legacy_model(model_id)`
- `find_spec(model_id)`

这和 Android 项目的 `HarnessModelRegistry.kt` 对应，用来让 UI、存储和下载逻辑逐步从直接依赖 `ModelInfo` 转向依赖 Harness spec。

## 7. 状态持久化

Android 侧用 `SharedPreferences` 保存选中模型、图片切片数和模型切换标记。

Python 脚本用 `JsonPreferenceStore` 代替，默认写入：

```text
harness_logic/data/.harness_state.json
```

默认 `root` 是 `harness_logic/data`，让这个 Python 子项目拥有独立的运行状态。也可以通过命令行指定：

```bash
python3 harness_logic.py --root /tmp/harness-test status
```

保存的 key 包括：

- `selected_model_id`
- `model_switched`
- `image_max_slice_nums`

这让脚本可以跨命令保留模型选择状态。

## 8. LlamaModelStore

`LlamaModelStore` 是模型存储层，对应 Android harness 中的 `LlamaModelStore.kt`。

它负责：

- 读取和写入选中模型。
- 处理模型切换标记。
- 保存和限制图片切片数量。
- 计算模型文件路径。
- 判断模型 artifact 是否完整。
- 删除选中模型文件。
- 执行旧模型目录迁移。

### 8.1 模型目录规则

模型文件默认放在：

```text
harness_logic/data/models/<model_id>/
```

例如：

```text
harness_logic/data/models/minicpm-v-4/ggml-model-Q4_K_M.gguf
harness_logic/data/models/minicpm-v-4/mmproj-model-f16.gguf
```

这对应 Android 侧每个模型一个子目录的布局。

### 8.2 availability 检查

`get_selected_model_availability()` 会返回：

- `gguf_missing`
- `support_artifact_missing`
- `complete`

其中：

- `gguf_missing` 检查 `llm` 文件是否存在。
- `support_artifact_missing` 检查除 `llm` 外的 required artifact 是否存在。
- `complete` 表示所有必需 artifact 都存在。

因此，视觉模型必须同时有 GGUF 和 mmproj；TTS 模型必须同时有 BaseLM 和 acoustic。

### 8.3 旧文件迁移

`migrate_legacy_layout_if_needed()` 复刻 Android 侧的迁移逻辑：

1. 如果旧文件平铺在 `models/` 下，把它移动到 `models/<model_id>/`。
2. 按 `LEGACY_FILE_RENAMES` 重命名历史文件。
3. 按 `STALE_MMPROJ_NAMES` 删除旧版不兼容 mmproj 文件和 `.tmp` 文件。

这部分逻辑用于兼容历史版本缓存，不影响新下载路径。

## 9. HarnessBackend 和 LlamaBackendAdapter

Android 侧的 `LlamaBackendAdapter` 会调用 `LlamaEngine`，再进入 JNI/native。

Python 脚本不能直接调用这些 Android 和 native 能力，所以实现了一个 mock backend：

```python
class HarnessBackend:
    ...

class LlamaBackendAdapter(HarnessBackend):
    ...
```

这个 backend 可以模拟：

- 加载模型文件。
- 卸载模型。
- 判断视觉 projector 是否加载。
- 预填充图片。
- 预填充视频帧。
- 清理上下文。
- 设置图片切片数。
- mock 文本生成。
- 取消生成。
- reset / destroy。

它的 `send_user_prompt()` 不做真实推理，只返回类似下面的文本：

```text
[mock backend] model=Llama-3.2-1B-Instruct-Q4_K_M.gguf predict_length=1024: 你好
```

这个设计的价值是：脚本可以验证 Harness 调用链是否跑通，但不会误导为真实模型能力。

## 10. LlamaDownloadManager

`LlamaDownloadManager` 在 Android 侧负责接入下载服务，实际下载逻辑仍在 `LlamaEngine.downloadModels()` 中。

Python 脚本里的 `LlamaDownloadManager` 不下载文件，只生成下载计划：

```python
build_download_plan()
```

它会把 `HarnessDownloadSource` 展开成真实 URL：

HuggingFace：

```text
https://huggingface.co/<repo>/resolve/<branch>/<remote_path>
```

ModelScope：

```text
https://www.modelscope.cn/models/<repo>/resolve/<branch>/<remote_path>
```

Direct：

```text
<direct url>
```

对于同一个 artifact，如果同时有 HF 和 ModelScope，就以 `race HuggingFace+ModelScope` 的形式展示。这对应 Android 下载器的“多源竞速”设计，但 Python 版本只展示计划，不执行竞速下载。

## 11. HarnessFacade

`HarnessFacade` 是脚本的统一入口，和 Android 侧的 `HarnessFacade.kt` 对齐。

它组合了三个组件：

```python
self.model_store = LlamaModelStore(root_dir)
self.backend = LlamaBackendAdapter()
self.download_manager = LlamaDownloadManager(self.model_store)
```

向外暴露的功能包括：

- 查询状态。
- 查询模型能力。
- 读取 / 设置选中模型。
- 检查模型是否下载完整。
- 读取 / 设置图片切片数。
- 加载 / 卸载模型。
- 图片 / 视频 prefill。
- 发送 prompt。
- 取消生成。
- 启动下载计划。
- 查询 artifact 文件名。
- 删除模型文件。

它的作用是把外部调用者和底层存储、下载、backend 细节隔离开。这正是 Harness 层在 Android 项目中的核心价值。

## 12. CLI 命令

脚本通过 `argparse` 提供命令行入口。

### 12.1 list

列出所有注册模型：

```bash
python3 harness_logic.py list
```

输出内容包括：

- model id
- display name
- family
- capabilities
- artifact 文件名

### 12.2 spec

输出某个模型的完整 Harness spec：

```bash
python3 harness_logic.py spec minicpm-v-4_6-instruct
```

适合检查 capability、artifact、下载源和 runtime hints。

### 12.3 select

保存选中模型：

```bash
python3 harness_logic.py select llama-3.2-1b-instruct
```

它会写入 `.harness_state.json`，并在模型变化时标记 `model_switched=True`。

### 12.4 status

查看当前模型状态：

```bash
python3 harness_logic.py status
```

它会显示：

- 当前选中模型
- backend state
- 图片切片数
- 是否下载完整
- 每个 artifact 的本地路径和存在状态
- 如果有 MD5，且文件存在，会计算并显示校验情况

### 12.5 download-plan

展示下载计划：

```bash
python3 harness_logic.py download-plan
```

这个命令不会下载文件，只输出每个 artifact 的候选下载 URL。

### 12.6 migrate

执行旧模型目录迁移：

```bash
python3 harness_logic.py migrate
```

会处理平铺模型文件、历史文件名和过期 mmproj。

### 12.7 touch-demo-files

创建极小的占位 artifact 文件：

```bash
python3 harness_logic.py touch-demo-files
```

用途是让 mock backend 能跑通 `load` 和 `prompt`。这些文件不是真模型，不能用于真实推理。

默认会在 `harness_logic/data` 中创建占位模型，不会写到仓库根目录：

```bash
python3 harness_logic.py select llama-3.2-1b-instruct
python3 harness_logic.py touch-demo-files
```

### 12.8 load

加载选中模型到 mock backend：

```bash
python3 harness_logic.py load
```

如果必需 artifact 不存在，会抛出 `FileNotFoundError`。

### 12.9 prompt

通过 mock backend 发送 prompt：

```bash
python3 harness_logic.py prompt 你好
```

如果当前 backend 还不是 `ModelReady`，命令会先调用 `load_selected_model()`。

### 12.10 delete

删除当前选中模型的 artifact 文件：

```bash
python3 harness_logic.py delete
```

只删除当前模型 spec 中声明的 artifact，不会删除整个 `models/` 目录。

## 13. 推荐测试流程

默认测试流程会使用 `harness_logic/data`，不会复用仓库根目录的 `models/`：

```bash
python3 harness_logic.py list
python3 harness_logic.py select llama-3.2-1b-instruct
python3 harness_logic.py status
python3 harness_logic.py download-plan
python3 harness_logic.py touch-demo-files
python3 harness_logic.py load
python3 harness_logic.py prompt 你好
```

如果需要把运行数据放到别处，可以继续显式传 `--root`。

这条链路会验证：

1. registry 能列出模型。
2. 选中模型状态能持久化。
3. 文件路径能按模型 id 派生。
4. 下载计划能从 spec 展开。
5. mock artifact 能让 backend 加载。
6. facade 能走到 mock prompt 流程。

## 14. 与 Android 原逻辑的对应关系

| Python 脚本 | Android 项目 |
| --- | --- |
| `ModelInfo` | `ModelInfo.kt` |
| `HarnessModelSpec` | `HarnessModelSpec.kt` |
| `HarnessModelRegistry` | `HarnessModelRegistry.kt` |
| `LlamaModelStore` | `LlamaModelStore.kt` |
| `LlamaDownloadManager.build_download_plan()` | `LlamaDownloadManager.kt` + `LlamaEngine.downloadModels()` 的下载源组织 |
| `HarnessBackend` | 可运行 mock 后端 |
| `LlamaBackendAdapter` | `LlamaBackendAdapter.kt`，但 Python 里不接 JNI |
| `HarnessFacade` | `HarnessFacade.kt` |
| `.harness_state.json` | Android `SharedPreferences` |
| `harness_logic/data/models/<model_id>/` | Android `filesDir/models/<model_id>/` |

## 15. 当前边界和限制

这个脚本有意保留以下边界：

- 不调用 Android `Context`。
- 不调用 `LlamaEngine`。
- 不加载 native library。
- 不调用 JNI。
- 不真实下载 GGUF。
- 不做真实模型推理。
- 不实现 Android 前台下载服务。
- 不实现 coroutine / Flow，只用 Python iterator 模拟 token streaming。

因此，它更适合作为 Harness 逻辑说明、命令行检查工具和后续 SDK 化拆分的参考骨架。

如果后续要让它变成真实 Python 推理脚本，需要增加一个真正的 backend，例如：

- llama.cpp Python binding
- llama-cpp-python
- 外部 HTTP runtime
- 自定义 native binding

届时只需要替换 `HarnessBackend` / `LlamaBackendAdapter`，上层的 `HarnessFacade`、`LlamaModelStore`、`HarnessModelRegistry` 可以基本保留。

## 16. 总结

`harness_logic.py` 的核心价值是把当前 Android 项目里已经散落在 Kotlin 层的 Harness 编排逻辑变成一个单文件、可运行、可检查的 Python 版本。

它完整覆盖了当前 Harness 的主要结构：

- 模型注册
- 模型 spec 生成
- artifact 管理
- capability 判断
- runtime hints
- 模型选择状态
- 本地文件完整性检查
- 旧文件迁移
- 下载源计划
- facade 统一入口
- backend 调用形态

它没有覆盖 native 推理和真实下载，这是刻意设计的边界。换句话说，它是该项目 Harness 层的可运行逻辑模型，而不是完整 Android 推理 runtime。
