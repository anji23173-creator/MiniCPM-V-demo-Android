# MiniCPM-V-demo-Android

`MiniCPM-V-demo-Android` 是一个端侧大模型 Android demo。当前主工程已经不只是原始 MiniCPM-V 聊天页，而是同时包含：

- Android 本地 GGUF 模型加载、下载、切换和推理。
- MiniCPM-V 图片理解和 `MiniCPM-V-4.6` 视频理解入口。
- VoxCPM2 TTS 页面。
- Harness 编排层、模型注册表、模型文件管理和下载适配。
- Android 侧 RAG、角色 Prompt、会话保存和 Memory 记录。
- `harness_logic/` Python 子项目，用于在桌面端验证 Harness、角色、session 和 mock backend 链路。

## 项目概览

- 项目类型：单模块 Android Application
- 应用包名：`com.example.minicpm_v_demo`
- 当前版本：`2.3`
- 最低系统版本：Android 7.0 (`minSdk 24`)
- 目标系统版本：Android 16 (`targetSdk 36`)
- 支持 ABI：`arm64-v8a`
- 主要技术栈：Kotlin、Android ViewBinding、JNI、CMake、llama.cpp-omni、Python 标准库测试

## 当前能力

- 本地文本模型对话。
- 多模态图片输入；只有视觉模型且 mmproj 成功加载后才显示/启用图片入口。
- 视频文件选择；视频理解路径由 `MiniCPM-V-4.6` 能力门控。
- 模型下载、选择、加载、卸载和删除。
- TTS 页面和 VoxCPM2 模型入口。
- 三种 Android 对话模式：普通对话、RAG、角色 RAG。
- RAG 资源、角色卡、剧情事件、prompt 模板和 fixtures 通过 `app/src/main/assets/harness/` 随 APK 打包。
- 应用启动时将 Harness assets 拷贝到应用私有目录 `filesDir/harness/`，运行时 session、memory、settings 等也写在该目录下。
- Python `harness_logic/` 可独立运行，用于模型 registry、下载计划、角色 Prompt、角色会话和 Memory 的本地 mock 验证。

注意：Android 主链路会调用真实 native runtime；`harness_logic/` 里的角色聊天仍以 mock backend 验证编排链路，不代表真实 LLM 推理。

## 项目结构

```text
.
├── app/
│   ├── src/main/assets/harness/
│   │   ├── manifest.json
│   │   ├── rag/
│   │   │   ├── index.json
│   │   │   ├── documents/
│   │   │   │   ├── novel_test/
│   │   │   │   └── world_cup/
│   │   │   └── documents_manifest.json
│   │   ├── characters/
│   │   │   ├── characters/
│   │   │   ├── story/
│   │   │   ├── prompts/
│   │   │   └── schemas/
│   │   ├── agent/
│   │   ├── fixtures/
│   │   └── roles/
│   ├── src/main/java/com/example/minicpm_v_demo/
│   │   ├── MainActivity.kt
│   │   ├── ModelManagerActivity.kt
│   │   ├── TtsActivity.kt
│   │   ├── LlamaEngine.kt
│   │   ├── ModelInfo.kt
│   │   ├── ModelDownloadService.kt
│   │   └── harness/
│   │       ├── HarnessFacade.kt
│   │       ├── HarnessModelRegistry.kt
│   │       ├── LlamaBackendAdapter.kt
│   │       ├── LlamaModelStore.kt
│   │       ├── character/
│   │       ├── chat/
│   │       ├── data/
│   │       ├── rag/
│   │       └── session/
│   ├── src/main/cpp/
│   ├── src/main/res/
│   └── build.gradle.kts
├── harness_logic/
│   ├── README.md
│   ├── run.sh
│   ├── cli.py
│   ├── registry.py
│   ├── facade.py
│   ├── character_system/
│   ├── data/
│   └── tests/
├── docs/
├── gradle/
├── build.gradle.kts
└── settings.gradle.kts
```

## Android 运行链路

```text
MiniCPMApplication
  -> AssetBootstrapper
      -> app assets/harness copied to filesDir/harness

MainActivity / ModelManagerActivity / TtsActivity
  -> HarnessFacade
      -> HarnessModelRegistry
      -> LlamaModelStore
      -> LlamaDownloadManager
      -> LlamaBackendAdapter
          -> LlamaEngine
              -> JNI
                  -> llama.cpp-omni
```

RAG 和角色链路在 Android 侧由 `AndroidRagOrchestrator` 编译 prompt：

```text
MainActivity
  -> AndroidRagOrchestrator
      -> RagSearchService + VectorIndex + HashEmbeddingModel
      -> CharacterPromptCompiler
      -> ChatTemplateRenderer
  -> HarnessFacade.sendUserPrompt(...)
```

会话与 Memory 由 `ChatSessionStore` 和 `MemoryStore` 写入 `filesDir/harness/sessions/` 与 `filesDir/harness/memory/`。

## 模型与资源

模型清单仍从 [app/src/main/java/com/example/minicpm_v_demo/ModelInfo.kt](app/src/main/java/com/example/minicpm_v_demo/ModelInfo.kt) 定义，并通过 [app/src/main/java/com/example/minicpm_v_demo/harness/HarnessModelRegistry.kt](app/src/main/java/com/example/minicpm_v_demo/harness/HarnessModelRegistry.kt) 转为 Harness spec。

当前注册模型包括 MiniCPM-V、MiniCPM5、VoxCPM2、Llama 3.2 1B、Qwen 等。模型文件不会随仓库提交，运行时由下载页或本地文件目录提供。

Harness 数据包在 [app/src/main/assets/harness/manifest.json](app/src/main/assets/harness/manifest.json) 描述，当前包含：

- hash n-gram RAG index。
- `world_cup` 和 `novel_test` 文档。
- 6 个角色和 28 条剧情事件。
- 角色 Prompt 模板、schema、agent fixtures 和默认 role。

## RAG 文本数据位置

需要让 LLM 通过 RAG 检索的文本、小说章节或 JSON 文档，放在：

```text
app/src/main/assets/harness/rag/documents/<dataset_name>/
```

当前已经打包进 APK 并可供检索的数据集在：

```text
app/src/main/assets/harness/rag/documents/novel_test/
app/src/main/assets/harness/rag/documents/world_cup/
```

RAG 检索依赖的索引和文档清单在：

```text
app/src/main/assets/harness/rag/index.json
app/src/main/assets/harness/rag/documents_manifest.json
```

应用启动时，`app/src/main/assets/harness/` 会复制到 Android 应用私有运行目录：

```text
filesDir/harness/
```

因此运行时 RAG 文档对应在：

```text
filesDir/harness/rag/documents/
```

## 构建与运行

基本要求：

- Android Studio
- Android SDK / NDK `27.0.12077973`
- CMake `4.1.2`
- arm64 真机或 arm64 模拟器

调试构建：

```bash
./gradlew :app:assembleDebug
```

默认调试 APK 输出：

```text
app/build/outputs/apk/debug/app-debug.apk
```

运行单元测试：

```bash
./gradlew :app:testDebugUnitTest
```

当前 APK 只打包 `arm64-v8a`。普通 `x86/x86_64` 模拟器通常不能直接验证 native 推理。

## Python Harness 子项目

`harness_logic/` 是独立 Python Harness 项目，默认运行目录是：

```text
harness_logic/data/
```

推荐从仓库根目录启动：

```bash
./harness_logic/run.sh
```

也可以直接调用 CLI：

```bash
python3 -m harness_logic list
python3 -m harness_logic character-list
python3 -m harness_logic character-prompt --character lu_jiangxian --input "玄谙究竟是什么？"
python3 -m unittest discover -s harness_logic/tests -v
```

Python 项目的详细说明见 [harness_logic/README.md](harness_logic/README.md)。

## 关键文件

- [app/build.gradle.kts](app/build.gradle.kts)：Android、NDK、CMake、ABI、依赖与动态 CPU so 构建配置。
- [app/src/main/java/com/example/minicpm_v_demo/MiniCPMApplication.kt](app/src/main/java/com/example/minicpm_v_demo/MiniCPMApplication.kt)：应用启动与 Harness assets 初始化。
- [app/src/main/java/com/example/minicpm_v_demo/MainActivity.kt](app/src/main/java/com/example/minicpm_v_demo/MainActivity.kt)：主聊天页、媒体选择、RAG 模式、会话保存。
- [app/src/main/java/com/example/minicpm_v_demo/LlamaEngine.kt](app/src/main/java/com/example/minicpm_v_demo/LlamaEngine.kt)：native 模型加载、推理、图片/视频 prefill 和 TTS runtime 接入。
- [app/src/main/java/com/example/minicpm_v_demo/harness/HarnessFacade.kt](app/src/main/java/com/example/minicpm_v_demo/harness/HarnessFacade.kt)：Android 页面访问 Harness 的统一入口。
- [app/src/main/java/com/example/minicpm_v_demo/harness/data/AssetBootstrapper.kt](app/src/main/java/com/example/minicpm_v_demo/harness/data/AssetBootstrapper.kt)：打包资源到运行目录的复制逻辑。
- [app/src/main/java/com/example/minicpm_v_demo/harness/rag/AndroidRagOrchestrator.kt](app/src/main/java/com/example/minicpm_v_demo/harness/rag/AndroidRagOrchestrator.kt)：普通 RAG 和角色 RAG Prompt 编译。
- [app/src/main/java/com/example/minicpm_v_demo/harness/character/CharacterPromptCompiler.kt](app/src/main/java/com/example/minicpm_v_demo/harness/character/CharacterPromptCompiler.kt)：角色身份、剧情边界、关系和记忆片段组装。
- [app/src/main/java/com/example/minicpm_v_demo/harness/session/ChatSessionStore.kt](app/src/main/java/com/example/minicpm_v_demo/harness/session/ChatSessionStore.kt)：Android 侧会话落盘。
- [harness_logic/README.md](harness_logic/README.md)：Python Harness 子项目说明。

## 文档索引

- [docs/Harness_Quickstart_Guide.md](docs/Harness_Quickstart_Guide.md)：Harness 快速认知。
- [docs/Harness/Inte_Harness.md](docs/Harness/Inte_Harness.md)：Harness 接入方案。
- [docs/Harness/Mini_Change.md](docs/Harness/Mini_Change.md)：阶段改动记录。
- [docs/Harness/Lightweight_Model_SDK_Roadmap.md](docs/Harness/Lightweight_Model_SDK_Roadmap.md)：轻量模型 SDK 化演进路线。

## 当前边界

- Android 主工程中，模型下载和本地文件路径仍保留对 `LlamaEngine` 旧逻辑的兼容，`HarnessModelRegistry` 还不是唯一事实源。
- Android RAG 使用当前打包的 hash n-gram 索引，不是外部 embedding 服务。
- `harness_logic/` 的 mock 对话只证明角色 Prompt、session 和 Memory 链路可运行，不证明真实模型输出质量。
- 真实推理验证需要在 arm64 设备上下载完整模型 artifact 后运行。
