# MiniCPM-V-demo-Android 接入 Harness 框架方案

## 最小改动建议

根据当前项目结构，接入 Harness 的最小改动方式不是替换现有 `LlamaEngine + JNI + llama.cpp-omni`，而是在 `Activity` 和 `LlamaEngine` 之间插入一层 Harness 抽象。

在这个项目里，Harness 最合适的角色不是新的推理引擎，而是统一编排层。它对上为 UI 提供稳定接口，对下封装现有本地 llama backend，并统一负责以下职责：

- 模型定义与能力声明
- 模型选择、下载、加载、卸载
- 会话创建、上下文清理、图片预填充、文本生成
- 后端路由与适配

最小接入路径建议如下：

1. 新增 `harness/` 包，只加抽象层，先不改 JNI 行为。
2. 定义 `HarnessBackend` 和 `HarnessFacade`。
3. 新增 `LlamaBackendAdapter`，内部直接复用现有 `LlamaEngine`。
4. 把 `MainActivity.kt` 和 `ModelManagerActivity.kt` 改成依赖 `HarnessFacade`，不再直接依赖 `LlamaEngine`。
5. `ModelInfo.kt` 先保留，只补一层到 Harness 模型描述的映射。

一句话概括：Harness 在这里应该是“编排层/适配层”，不是“替代引擎层”。

## 当前进度

截至 2026 年 7 月 17 日，当前仓库的实际状态是：

- 阶段一已完成
- 阶段二已开始，但尚未完成
- 阶段三已开始，但尚未完成

已完成的阶段二内容：

- 新增 `LlamaModelStore`
- 新增 `LlamaDownloadManager`
- `HarnessFacade` 已开始把模型存储和下载职责委托给这两层
- `ModelDownloadService` 已改为通过 `LlamaDownloadManager` 执行下载

尚未完成的阶段二内容：

- `LlamaRuntime` 还未从 `LlamaEngine` 中拆出
- `LlamaBackendAdapter` 仍直接包裹 `LlamaEngine`
- 运行时职责仍主要集中在 `LlamaEngine.kt`

已完成的阶段三内容：

- 新增 `HarnessModelRegistry`
- `HarnessModelSpec` 已扩展为包含 `family`、`artifacts`、`downloadSources`、`runtimeHints`
- `LlamaModelStore` 已开始按 registry + artifact 列表判断模型文件完整性
- `ModelManagerActivity` 已开始通过 registry 暴露的模型列表工作
- `LlamaEngine.getSelectedModel(...)` 已开始通过 registry 解析模型 ID

尚未完成的阶段三内容：

- `ModelInfo` 仍然是 registry 的底层来源，而不是纯兼容层
- 下载执行仍主要依赖旧 `ModelInfo` 字段和 `LlamaEngine.downloadModels(...)`
- `HarnessModelRegistry` 还没有成为所有模型相关逻辑的唯一事实来源

## 1. 目标与前提

本文基于以下假设来设计方案：

- `Harness` 指一个新的推理编排/接入框架，用来统一管理模型元数据、模型下载、模型加载、会话推理和多后端切换。
- 当前项目已有的 `LlamaEngine + JNI + llama.cpp-omni` 仍然保留，先作为 Harness 的一个底层执行后端接入，而不是一次性整体替换。
- 第一阶段目标不是“重写项目”，而是“在现有 Android 工程中插入一层 Harness 抽象”，让后续可以继续接入其他模型家族或其他执行后端。

如果这里的 `Harness` 实际上是某个特定第三方 SDK / 平台产品，那么本文的分层思路仍然适用，但依赖接入、认证方式、网络调用协议和生命周期管理需要再按该产品文档细化。

## 2. 当前项目现状

这个仓库当前不是简单的 Android UI 项目，而是四层耦合结构：

1. Android UI 层
   - `MainActivity.kt`
   - `ModelManagerActivity.kt`
2. 模型元数据与下载层
   - `ModelInfo.kt`
   - `ModelDownloadService.kt`
   - `LlamaEngine.kt` 中的下载与路径管理逻辑
3. Kotlin 推理编排层
   - `LlamaEngine.kt`
4. Native 执行层
   - `app/src/main/cpp/llama_jni.cpp`
   - `app/src/main/cpp/CMakeLists.txt`
   - 根目录外部引入的 `llama.cpp-omni`

当前实现有几个明显特征：

- `ModelInfo.kt` 里直接描述模型文件名、下载源、`gguf/mmproj/acoustic` 等细节。
- `LlamaEngine.kt` 同时承担了模型选择、文件路径、模型是否存在、下载、加载、会话推理、Native 调用等多种职责。
- `llama_jni.cpp` 明确绑定了 MiniCPM-V / mtmd / voxcpm2 的能力模型。
- `CMakeLists.txt` 直接链接 `llama`、`mtmd`、`voxcpm2_runtime`，说明当前 Native 构建也是 MiniCPM 家族导向。

结论：Harness 不应直接“插进 Activity 里”，而应作为 `UI` 和 `LlamaEngine/JNI` 之间的新中间层。

## 3. 接入目标

接入 Harness 后，建议达到以下状态：

- UI 层只依赖 `HarnessSession`、`HarnessModelManager` 这类抽象接口，不直接依赖 `LlamaEngine` 的实现细节。
- `ModelInfo` 从“MiniCPM 专属配置”演进为“通用模型清单 + 能力声明”。
- `LlamaEngine` 从“大一统类”收缩为一个 `LlamaBackendAdapter`，只负责本地 llama.cpp Native 推理。
- 后续要接入新模型家族、云端推理服务或新的 Native Runtime 时，只新增 Harness adapter，而不是继续堆积条件分支。

## 4. 推荐架构

建议增加一层 `harness` 包，形成如下结构：

```text
UI(Activity)
  -> HarnessFacade
      -> HarnessModelRegistry
      -> HarnessDownloadManager
      -> HarnessSessionManager
      -> HarnessBackend
           |- LlamaBackendAdapter
           |- FutureRemoteBackendAdapter
           |- FutureOtherNativeBackendAdapter
```

建议新增的核心抽象：

### 4.1 HarnessModelSpec

作用：替代当前 `ModelInfo` 的强耦合描述。

建议字段：

- `id`
- `displayName`
- `family`
- `capabilities`
- `artifacts`
- `downloadSources`
- `runtimeHints`

其中：

- `family` 用于区分 `minicpm_v`、`minicpm_text`、`voxcpm2`、未来其他家族。
- `capabilities` 用于声明 `text`、`vision`、`video`、`tts` 等能力。
- `artifacts` 用于声明模型需要哪些文件，而不是写死为 `gguf + mmproj + acoustic`。
- `runtimeHints` 用于声明是否需要 `mtmd`、默认上下文长度、切图参数、线程数等。

### 4.2 HarnessBackend

定义统一后端接口，例如：

```kotlin
interface HarnessBackend {
    suspend fun prepare(model: HarnessModelSpec)
    suspend fun load(model: HarnessModelSpec, localArtifacts: Map<String, String>)
    suspend fun unload()
    suspend fun createSession(sessionId: String)
    suspend fun prefillImage(sessionId: String, imagePath: String)
    suspend fun generate(sessionId: String, prompt: String): Flow<String>
    suspend fun clearSession(sessionId: String)
    fun supports(capability: String): Boolean
}
```

第一阶段只实现：

- `LlamaBackendAdapter`

它内部继续调用现有 `LlamaEngine` / JNI。

### 4.3 HarnessFacade

作用：给 `MainActivity` 和 `ModelManagerActivity` 提供稳定入口。

它负责：

- 当前模型选择
- 模型是否已下载
- 下载任务启动/取消
- 模型加载/卸载
- 会话创建与清理
- 文本生成、图片预填充、能力判断

这样 Activity 层无需知道底层是 `LlamaEngine` 还是未来其他 Harness backend。

## 5. 分阶段改造方案

## 阶段一：先抽象，不改底层推理

目标：不碰 JNI 行为，只整理 Kotlin 层边界。

改造内容：

1. 新增 `app/src/main/java/com/example/minicpm_v_demo/harness/` 包。
2. 定义：
   - `HarnessModelSpec`
   - `HarnessArtifact`
   - `HarnessCapability`
   - `HarnessBackend`
   - `HarnessFacade`
3. 新建 `LlamaBackendAdapter`，内部复用现有 `LlamaEngine`。
4. 把 `MainActivity.kt` 对 `LlamaEngine` 的直接依赖替换为 `HarnessFacade`。
5. 把 `ModelManagerActivity.kt` 中的模型存在检查、下载、加载逻辑切到 `HarnessFacade`。

收益：

- 改动风险最低。
- UI 层先稳定。
- 后续接入其他 backend 时不用再动 Activity。

## 阶段二：拆分 LlamaEngine 职责

目标：把当前 `LlamaEngine.kt` 中混在一起的职责拆开。

建议拆分为：

- `LlamaModelStore`
  - 路径管理
  - 文件存在性检查
  - 旧目录迁移
- `LlamaDownloadManager`
  - 文件下载
  - MD5 校验
  - 断点续传
- `LlamaRuntime`
  - load / unload / generate / image prefill
  - 纯运行时状态管理
- `LlamaBackendAdapter`
  - 把上面三个能力拼成 HarnessBackend

这样可以消除 `LlamaEngine` 既像 service、又像 repository、又像 runtime controller 的问题。

## 阶段三：模型定义泛化

目标：把当前 `ModelInfo.kt` 从 MiniCPM 专用结构改造成通用 Harness 模型注册表。

建议处理方式：

1. 保留旧 `ModelInfo` 一段时间作为兼容层。
2. 新增 `HarnessModelRegistry` 作为新的模型清单入口。
3. 把旧字段映射成通用 artifact 结构，例如：
   - `gguf` -> `artifact(type = "llm")`
   - `mmproj` -> `artifact(type = "vision_projector")`
   - `acoustic` -> `artifact(type = "acoustic")`
4. `modelsExist()` 这类逻辑从“判断某几个固定字段是否存在”改成“按 artifact 列表判断所有 required artifact 是否存在”。

这样后续接入其他模型时，不需要继续在 `ModelInfo` 上打补丁。

## 阶段四：Native 层按 backend 能力解耦

目标：让 JNI 和 CMake 不再默认绑定 MiniCPM 家族。

当前问题：

- `llama_jni.cpp` 里有明确的 MiniCPM-V 版本逻辑。
- `loadMmproj()`、`setMinicpmvVersionNative()`、`setImageMaxSliceNumsNative()` 都体现了 MiniCPM 专有路径。
- `CMakeLists.txt` 直接链接 `mtmd`、`voxcpm2_runtime`。

建议方案：

1. 保留现有 `llama_jni.cpp` 作为 `MiniCPMLlamaBackend` 的 native 实现。
2. 后续如果 Harness 需要支持其他 native backend，则新增新的 JNI bridge 文件，而不是继续往 `llama_jni.cpp` 塞分支。
3. 在 Kotlin 层通过 `HarnessBackend` 选择不同后端，不把 backend 选择逻辑压到 JNI 里。

第一阶段不建议改这层，因为风险高、验证成本大。

## 6. 建议落地到哪些文件

### 6.1 新增文件

建议新增：

- `app/src/main/java/com/example/minicpm_v_demo/harness/HarnessFacade.kt`
- `app/src/main/java/com/example/minicpm_v_demo/harness/HarnessBackend.kt`
- `app/src/main/java/com/example/minicpm_v_demo/harness/HarnessModelSpec.kt`
- `app/src/main/java/com/example/minicpm_v_demo/harness/HarnessModelRegistry.kt`
- `app/src/main/java/com/example/minicpm_v_demo/harness/LlamaBackendAdapter.kt`

### 6.2 首批需要调整的现有文件

- `app/src/main/java/com/example/minicpm_v_demo/MainActivity.kt`
  - 把 `engine` 访问改为 `harnessFacade`
- `app/src/main/java/com/example/minicpm_v_demo/ModelManagerActivity.kt`
  - 模型管理动作改为调用 `harnessFacade`
- `app/src/main/java/com/example/minicpm_v_demo/ModelInfo.kt`
  - 先增加与 `HarnessModelSpec` 的映射能力
- `app/src/main/java/com/example/minicpm_v_demo/LlamaEngine.kt`
  - 收缩为底层 adapter 依赖，减少 UI 直接耦合
- `app/src/main/java/com/example/minicpm_v_demo/ModelDownloadService.kt`
  - 下载入口可逐步迁移到 `HarnessDownloadManager`

## 7. 推荐的最小可行接入路径

如果目标是“先把 Harness 框架接进来，再逐步迁移”，建议按这个最小路径执行：

1. 新增 `HarnessBackend` 和 `HarnessFacade` 抽象。
2. 新增 `LlamaBackendAdapter`，内部完全复用现有 `LlamaEngine`。
3. 让 `MainActivity` 改为只通过 `HarnessFacade` 发起：
   - 加载模型
   - 发送消息
   - 图片预填充
   - 清理上下文
4. 让 `ModelManagerActivity` 改为只通过 `HarnessFacade` 发起：
   - 模型切换
   - 下载
   - 删除
   - 是否已下载判断
5. `ModelInfo` 暂时保留，但补一层 `toHarnessSpec()` 映射。

这样做的意义是：

- 接入速度最快。
- 现有 JNI 和下载逻辑基本不用动。
- 可以先验证 Harness 分层是否适合这个项目，再决定是否进一步替换下载器或 runtime。

## 8. 风险点

### 8.1 会话状态迁移风险

当前 `LlamaEngine` 维护了较多运行时状态，例如：

- 当前模型
- 是否 ready
- 图像预填充状态
- 生成中状态

如果 Harness 接入时把这些状态同时保留在 `Activity`、`HarnessFacade`、`LlamaEngine` 三处，容易状态漂移。建议以 `HarnessFacade` 为唯一对外状态源。

### 8.2 模型工件定义仍然过于固定

当前模型文件结构已经不是单一 `gguf`，而是：

- 文本模型：`gguf`
- 多模态模型：`gguf + mmproj`
- TTS 模型：`gguf + acoustic`

如果 Harness 抽象仍然写死字段，后续扩展价值会很低。建议第一版就用 artifact list。

### 8.3 Native 能力判断耦合

例如 `MiniCPM-V-4.6` 的 `n_ctx`、视频理解、slice 参数等，当前部分逻辑落在 native 层。Harness 设计时必须允许 `runtimeHints` 下沉到 backend，而不是全部留在 UI 层。

### 8.4 下载与前台服务耦合

`ModelDownloadService.kt` 目前和 `LlamaEngine.downloadModels()` 是直接耦合的。若未来 Harness 要统一下载多种模型后端，建议把 service 保留，但把真正下载逻辑抽到 Harness 层。

## 9. 验证方案

建议按以下顺序验证：

1. 编译验证
   - `./gradlew :app:assembleDebug`
2. 模型管理验证
   - 模型列表正常展示
   - 切换模型不崩溃
   - 已下载/未下载状态正确
3. 推理验证
   - 文本模型可正常生成
   - 多模态模型可加载图片并生成
   - TTS 模型入口不受影响
4. 生命周期验证
   - 旋转屏幕
   - 切后台再回来
   - 下载进行中退出页面
5. 回归验证
   - 原有 MiniCPM-V-4 / 4.6 / MiniCPM5 / VoxCPM2 路径不退化

## 10. 结论

对这个项目来说，接入 Harness 的正确方式不是直接替换 `LlamaEngine`，而是先在 `Activity` 与 `LlamaEngine` 之间建立一层稳定的 Harness 抽象，把：

- 模型定义
- 下载管理
- 会话管理
- 后端执行

从当前的单类耦合结构中拆出来。

最稳妥的首期方案是：

- 先新增 Harness 抽象层
- 先让 `LlamaEngine` 成为 Harness 的一个 adapter
- 先改 Kotlin 层边界
- 暂不大改 JNI / CMake

这样可以在较低风险下完成框架接入，并为后续扩展其他模型家族、远端服务或其他推理后端留出明确演进路径。
