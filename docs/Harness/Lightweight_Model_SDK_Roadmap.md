# 轻量模型通过 Harness 接入方案与跨平台游戏 LLM SDK 演进路线

## 1. 目标

本文回答两个问题：

1. 在当前项目已经完成最小 Harness 接入的前提下，轻量模型如何以较低风险接入这个项目。
2. 如果目标从“Android Demo”继续升级为“跨平台游戏可复用的 LLM SDK”，后续应该如何演进，才能增强通用性。

这里的“轻量模型”主要指：

- 文本优先的小参数模型
- 不依赖 `mmproj` 的 GGUF 模型
- 资源占用更低、适合端侧和游戏场景的模型

典型例子包括当前 `ModelInfo.kt` 中已经出现的：

- `Llama 3.2 1B Instruct`
- `Qwen 0.6B/0.8B` 一类文本模型
- 未来其他 0.5B ~ 3B 量级的 GGUF 文本模型

## 2. 当前项目对轻量模型已经具备的基础

从当前代码看，这个项目已经具备一部分轻量模型接入基础，不需要从零开始：

- `ModelInfo.kt` 已支持“仅 GGUF、无 mmproj”的模型定义
- `LlamaEngine.modelsExist()` 已支持 text-only 模型判断
- `LlamaEngine.loadModel(pathToModel, pathToMmproj)` 已支持 `mmproj` 为空
- 当前最小 Harness 已有：
  - `HarnessModelSpec`
  - `HarnessCapability`
  - `HarnessFacade`
  - `LlamaBackendAdapter`

这意味着：

- 轻量文本模型并不需要先改 JNI 才能尝试接入
- 第一阶段可以继续复用当前 `LlamaBackendAdapter`
- 真正需要补的，主要是模型注册、能力约束、运行参数抽象，以及后续 SDK 化边界

## 3. 轻量模型通过 Harness 接入的最小路径

如果目标是“尽快让轻量模型通过 Harness 接入当前 App”，建议按以下路径执行。

### 3.1 只接入 text-only GGUF 模型

第一批建议只接入下面这类模型：

- 只有一个 GGUF 主文件
- 不依赖视觉 projector
- 不依赖 acoustic bundle
- 能在当前 `llama.cpp-omni` 主链路下正常加载

原因：

- 改动最小
- 不碰 `mtmd`
- 不碰 `voxcpm2`
- 不需要扩展 UI 的图片/视频/TTS 行为

### 3.2 通过 Harness 统一定义模型能力

虽然当前 `HarnessModelSpec` 已经有 `capabilities`，但要让轻量模型真正稳定接入，还需要把“能力声明”作为主约束，而不是继续依赖模型名或 `mmprojFileName == null` 这种隐式规则。

建议补充的能力判断规则：

- `TEXT`
  - 所有可聊天模型默认具备
- `VISION`
  - 必须有 `vision_projector` artifact
- `VIDEO`
  - 必须有 `VISION`，并且 runtime 明确支持多帧预填充
- `TTS`
  - 必须有 `acoustic` artifact

这样轻量模型接入时，UI 行为会自动收敛为：

- 隐藏图片按钮
- 隐藏图片切片按钮
- 禁用视频路径
- 保留纯文本对话路径

### 3.3 通过 HarnessModelRegistry 继续接管模型注册

当前项目已经新增 `HarnessModelRegistry`，但它还没有成为所有模型逻辑的唯一事实来源。要让轻量模型以 Harness 方式稳定接入，下一步应继续强化它：

职责：

- 汇总所有模型定义
- 暴露 `HarnessModelSpec`
- 暴露每个模型的 artifact 清单
- 暴露推荐运行参数

此时旧 `ModelInfo` 可以作为兼容层保留，但 UI、下载和运行时逻辑应逐步从 `ModelInfo` 转向 `HarnessModelRegistry`。

### 3.4 为轻量模型增加 runtime hints

轻量模型虽然共用 GGUF 路径，但实际运行参数并不一定相同。为了避免继续把运行差异散落在 `LlamaEngine` 或 UI 里，建议给 Harness 模型定义增加 `runtimeHints`，至少包括：

- `defaultContextSize`
- `defaultPredictLength`
- `recommendedThreads`
- `supportsSystemPrompt`
- `promptFormat`
- `stopTokens`

对轻量模型尤其重要的是：

- 不能沿用所有 MiniCPM-V 的默认上下文和生成策略
- 不同家族模型的 chat template 可能不同
- 如果要作为 SDK 给游戏使用，prompt 格式和停词必须可配置

### 3.5 让 LlamaBackendAdapter 成为“通用文本 backend”，而不是“MiniCPM adapter”

当前 `LlamaBackendAdapter` 虽然已经是 Harness backend，但本质上还是转发到当前 `LlamaEngine`。如果要让轻量模型更自然地接入，下一步不必立刻重写 backend，但至少要开始区分两类逻辑：

- 通用 GGUF 文本逻辑
- MiniCPM-V 专有多模态逻辑

建议方向：

1. 保留现有 `LlamaBackendAdapter`
2. 把 `LlamaEngine` 中和 `mmproj`、视频、多模态相关的行为逐步收缩
3. 把“纯文本 GGUF”路径整理成更通用的 `TextLlamaRuntime`

这样轻量模型接入时，就不再显得是“借住在 MiniCPM demo 里”，而是成为正式支持的一类 backend capability。

## 4. 推荐的轻量模型接入阶段

### 阶段 A：模型可配置化

目标：

- 让 `Llama 3.2 1B`、`Qwen 0.6B/0.8B` 这类模型通过 Harness 被识别为标准 text-only 模型

当前状态：

- `HarnessModelRegistry` 已存在
- `HarnessModelSpec` 已包含 `runtimeHints`

接下来建议：

- UI 只根据 `capabilities` 决定功能可见性
- 下载和运行时继续从 registry 读取模型信息

### 阶段 B：下载逻辑泛化

目标：

- 不再用“gguf/mmproj/acoustic”固定字段驱动下载

建议修改：

- 新增 `HarnessDownloadManager`
- 下载按 `artifacts` 列表执行
- 校验规则跟随 artifact 元数据，而不是写死字段名

这样轻量模型只需要定义一个 `llm` artifact 就能完整接入。

### 阶段 C：Prompt 与模板能力抽象

目标：

- 支持不同文本模型家族的 prompt 模板差异

建议修改：

- 把 prompt 组织逻辑从 `LlamaEngine` 中进一步提炼
- 在 Harness 层增加：
  - `ChatTemplate`
  - `PromptFormatter`
  - `RoleMapping`

这是轻量模型真正大规模接入前必须做的，因为：

- Llama 家族
- Qwen 家族
- MiniCPM 家族

并不一定共享同一套会话模板。

## 5. 轻量模型接入后，在 App 中的实际体现

完成上面的改造后，App 侧会出现以下实际效果：

### 5.1 模型页

- 模型列表中可以同时出现多模态模型和轻量文本模型
- 选择轻量模型后，不再要求 `mmproj`
- 下载只拉取该模型所需的单个 GGUF artifact

### 5.2 聊天页

- 加载轻量模型后，页面自动退化为纯文本聊天模式
- 图片、视频、多模态入口自动隐藏或禁用
- 对用户来说，模型切换流程不变，但能力边界更清晰

### 5.3 后续扩展

- 新增一个轻量模型，不再需要到多个页面里补条件分支
- 主要只需要：
  - 注册模型
  - 定义 artifact
  - 定义 capability
  - 定义 runtime hints

## 6. 如果目标升级为“跨平台游戏 LLM SDK”，Harness 应扮演什么角色

一旦目标从“Android App 内部的编排层”升级为“给游戏接入的跨平台 LLM SDK”，Harness 的角色就要从 App Facade 升级为 SDK Kernel。

也就是说：

- 在当前项目里，Harness 主要是 App 内的中间层
- 在未来 SDK 里，Harness 应该成为平台无关的核心编排内核

它应该负责：

- 模型注册
- artifact 管理
- backend 选择
- session 管理
- prompt 格式化
- 流式输出
- 能力检查
- 资源调度
- 可观测性

而不应该继续承担：

- Android Activity 生命周期细节
- Android UI 控件逻辑
- 平台专有存储与权限流程

## 7. 面向跨平台游戏 LLM SDK 的演进方向

如果最终目标是“构建跨平台游戏的 LLM SDK”，建议从现在的最小 Harness 继续向下列结构演进。

### 7.1 把 HarnessCore 从 Android 工程中拆出来

建议形成三层：

```text
platform UI / game binding
    -> sdk facade
        -> harness core
            -> backend adapters
                -> native runtimes
```

其中：

- `harness core`
  - 不依赖 Android API
  - 只保留模型、会话、backend、prompt、artifact 等纯核心逻辑
- `sdk facade`
  - 提供给 Unity / Unreal / Godot / Android / iOS 的稳定 API
- `platform binding`
  - 处理平台权限、文件路径、线程调度、日志桥接

### 7.2 定义稳定的跨平台 SDK API

建议后续把当前 `HarnessFacade` 演进为更通用的 SDK API，例如：

```kotlin
interface LlmSdk {
    suspend fun installModel(modelId: String)
    suspend fun loadModel(modelId: String)
    suspend fun unloadModel()
    suspend fun createSession(sessionId: String, config: SessionConfig)
    suspend fun sendMessage(sessionId: String, message: ChatMessage): Flow<TokenChunk>
    suspend fun interrupt(sessionId: String)
    suspend fun deleteModel(modelId: String)
    fun listModels(): List<ModelDescriptor>
}
```

这个 API 的关键点是：

- 不暴露 Android 页面语义
- 不暴露特定模型文件名字段
- 不暴露 MiniCPM 专属概念

### 7.3 统一模型包格式

如果要跨平台复用，模型定义不能长期依赖硬编码 Kotlin 列表。建议引入统一 manifest，例如：

- `model.json`

至少描述：

- 模型 ID
- 家族
- 版本
- capabilities
- artifacts
- prompt template
- 运行参数
- 设备要求

这样 Android、iOS、Windows、macOS、主机端都可以消费同一份模型描述。

### 7.4 解耦平台文件系统与下载器

游戏 SDK 通常会落到多个运行环境：

- Android
- iOS
- Windows
- macOS
- 未来可能还有 console 或 embedded 环境

因此后续必须把下面这些能力抽接口：

- 文件系统
- 下载器
- 缓存目录
- 校验器
- 后台任务/前台任务模型

建议新增：

- `ArtifactStore`
- `ArtifactDownloader`
- `PlatformPaths`
- `IntegrityVerifier`

这样才能把当前 `ModelDownloadService + filesDir + SharedPreferences` 这类 Android 特定实现逐步隔离出去。

### 7.5 把会话模型改成游戏友好的 Session 架构

游戏场景和 Demo 聊天场景不一样，通常更关心：

- 多 NPC 并发会话
- 可中断生成
- 上下文裁剪
- Persona / 世界观 / 任务状态注入
- 较强的可控性与可重复性

因此后续建议把 Harness 的会话层升级为：

- `SessionManager`
- `SessionState`
- `ConversationMemory`
- `PromptComposer`

对游戏 SDK 来说，这层比“下载模型页面”更重要，因为业务价值主要在运行时编排，而不是单个 Demo 页面。

### 7.6 增加后端多样性，而不是绑定单一 llama runtime

如果目标是通用 SDK，不能把未来限制死在当前 `llama.cpp-omni` 上。

建议 Harness backend 长期支持以下扩展点：

- `LlamaCppBackend`
- `MiniCpmVisionBackend`
- `OnnxBackend`
- `MlcBackend`
- `RemoteFallbackBackend`

游戏项目常见需求是：

- 低端机本地小模型
- 中高端机本地较强模型
- 复杂任务走远端

所以 SDK 必须允许 backend route，而不是只有单一硬编码路径。

### 7.7 增加可观测性与性能配置

对游戏 SDK，必须支持：

- 首次加载耗时
- token/s
- 预填充耗时
- 峰值内存
- backend 选择原因
- 会话级错误码

建议在 Harness 中加入：

- `MetricsCollector`
- `TraceEvent`
- `SdkError`
- `DeviceProfile`

这样后续接 Unity/Unreal 时，才方便做调优和线上归因。

## 8. 为了增强通用性，建议的后续改造优先级

如果从“当前最小 Harness”继续往“跨平台游戏 LLM SDK”演进，建议优先级如下。

### 优先级 1：模型与 artifact 泛化

先做：

- `HarnessModelRegistry`
- `runtimeHints`
- artifact-list 驱动下载与校验

原因：

- 这是轻量模型和多模型接入的基础
- 也是未来 SDK 使用统一 manifest 的前提

### 优先级 2：拆分 LlamaEngine

拆成：

- model store
- download manager
- runtime
- prompt formatter

原因：

- 当前 `LlamaEngine` 职责太重，不利于 SDK 化复用

### 优先级 3：提炼平台无关 HarnessCore

目标：

- 让核心层不依赖 Android

原因：

- 不先去 Android 依赖，跨平台 SDK 只是口号，无法真实复用

### 优先级 4：定义稳定 SDK API 和 C ABI/桥接层

如果要服务 Unity/Unreal/Godot，最终一般需要：

- C ABI
- JNI bridge
- Swift/ObjC bridge
- C# wrapper

HarnessCore 最好先保持纯核心逻辑，再从外层生成这些桥接。

### 优先级 5：游戏场景特化能力

包括：

- 多 NPC 会话
- prompt slot 注入
- persona system
- interrupt/resume
- deterministic config

这部分更接近真正的游戏 SDK 产品能力。

## 9. 结论

对当前项目来说，轻量模型通过 Harness 接入的最优路径不是重写 native，而是：

- 先把轻量模型当作标准 text-only GGUF 模型
- 通过 Harness 的 capability、artifact、runtime hints 管理它们
- 继续复用当前 `LlamaBackendAdapter`

而如果目标升级为“跨平台游戏 LLM SDK”，那么后续重点就不再是“把更多模型塞进 Demo”，而是把当前最小 Harness 演进成：

- 平台无关的 HarnessCore
- 统一模型 manifest
- 通用 Session 架构
- 多 backend 路由层
- 可供 Unity/Unreal/Godot 等复用的稳定 SDK API

一句话总结：

- 轻量模型接入阶段，Harness 是模型编排层
- SDK 化阶段，Harness 应升级为跨平台 LLM 内核
