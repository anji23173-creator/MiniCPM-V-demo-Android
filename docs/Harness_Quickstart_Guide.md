# MiniCPM-V-demo-Android 与 Harness 快速上手说明

## 1. 这份文档解决什么问题

如果你现在对下面这些问题还不够清楚：

- 这个项目整体是怎么组织的
- 这个 App 现在已经能做什么
- 推理链路是怎么跑起来的
- Harness 在这里到底是什么
- Harness 已经做了什么，没做什么
- 后续如果要扩展轻量模型或做 SDK，应该从哪里入手

那么这份文档的目标就是让你快速建立整体认知。

## 2. 先用一句话理解这个项目

这个项目本质上是一个 **Android 端本地模型 Demo**：

- 上层是 Android 页面
- 中间是 Kotlin 编排逻辑
- 下层通过 JNI 调本地推理 runtime
- 当前主执行后端是 `llama.cpp-omni`

它不是纯 UI 项目，也不是纯 Native 项目，而是一个“Android + Kotlin + JNI + 本地模型 runtime”的组合工程。

## 3. 这个项目现在能做什么

从现有代码和模型定义看，这个项目当前主要支持三类能力：

### 3.1 纯文本模型聊天

例如：

- `MiniCPM5-1B`
- `Llama 3.2 1B Instruct`
- `Qwen` 小模型

这类模型只需要一个 GGUF 文件，加载后就是纯文本对话。

### 3.2 多模态图片理解

例如：

- `MiniCPM-V-4`
- `MiniCPM-V-4.6`

这类模型除了主 GGUF，还需要 `mmproj` 文件，支持图片预填充，再基于图片进行问答。

### 3.3 部分模型的额外能力

- `MiniCPM-V-4.6` 支持视频理解路径
- `VoxCPM2` 走 TTS 路径

也就是说，这个项目不是“只有一个聊天模型”，而是已经包含：

- 文本模型
- 多模态模型
- 视频路径
- TTS 路径

只是这些能力目前还没有被完全抽象成统一 SDK 结构。

## 4. 这个项目的核心目录和文件怎么理解

如果只想快速抓主干，优先看下面这些文件。

### 4.1 UI 层

- [MainActivity.kt](../app/src/main/java/com/example/minicpm_v_demo/MainActivity.kt)
- [ModelManagerActivity.kt](../app/src/main/java/com/example/minicpm_v_demo/ModelManagerActivity.kt)
- [TtsActivity.kt](../app/src/main/java/com/example/minicpm_v_demo/TtsActivity.kt)

作用：

- `MainActivity` 负责聊天页
- `ModelManagerActivity` 负责模型选择、下载、加载、删除
- `TtsActivity` 负责 TTS 相关页面

### 4.2 模型定义层

- [ModelInfo.kt](../app/src/main/java/com/example/minicpm_v_demo/ModelInfo.kt)

作用：

- 定义有哪些模型
- 每个模型需要哪些文件
- 模型从哪里下载
- 是否是 text-only / vision / tts

可以把它理解为当前项目的“模型清单”。

### 4.3 编排与运行时层

- [LlamaEngine.kt](../app/src/main/java/com/example/minicpm_v_demo/LlamaEngine.kt)

作用非常重，当前它同时负责：

- 当前模型选择
- 模型文件路径
- 模型是否存在
- 模型下载
- 模型加载/卸载
- 文本生成
- 图片预填充
- 视频预填充
- Native 调用入口

所以它是当前项目里最核心、也最耦合的类。

### 4.4 下载服务层

- [ModelDownloadService.kt](../app/src/main/java/com/example/minicpm_v_demo/ModelDownloadService.kt)

作用：

- 把大模型下载放到前台服务里执行
- 保证切后台后下载还能继续
- 负责通知栏和下载状态传播

### 4.5 Native 层

- [llama_jni.cpp](../app/src/main/cpp/llama_jni.cpp)
- [CMakeLists.txt](../app/src/main/cpp/CMakeLists.txt)

作用：

- `llama_jni.cpp` 是 Kotlin 调本地推理的 JNI 桥
- `CMakeLists.txt` 负责 native 构建和链接

这里已经明显包含 MiniCPM-V、多模态、voxcpm2 等定制逻辑。

### 4.6 当前新增的 Harness 层

- [HarnessFacade.kt](../app/src/main/java/com/example/minicpm_v_demo/harness/HarnessFacade.kt)
- [HarnessModelRegistry.kt](../app/src/main/java/com/example/minicpm_v_demo/harness/HarnessModelRegistry.kt)
- [HarnessBackend.kt](../app/src/main/java/com/example/minicpm_v_demo/harness/HarnessBackend.kt)
- [LlamaBackendAdapter.kt](../app/src/main/java/com/example/minicpm_v_demo/harness/LlamaBackendAdapter.kt)
- [HarnessModelSpec.kt](../app/src/main/java/com/example/minicpm_v_demo/harness/HarnessModelSpec.kt)
- [LlamaModelStore.kt](../app/src/main/java/com/example/minicpm_v_demo/harness/LlamaModelStore.kt)
- [LlamaDownloadManager.kt](../app/src/main/java/com/example/minicpm_v_demo/harness/LlamaDownloadManager.kt)

这是当前 Harness 层的主结构，用来把 UI 和 `LlamaEngine` 之间隔出边界，并开始把模型存储与下载职责从 `LlamaEngine` 中拆出来。

## 5. 这个项目的真实调用链路是什么

如果以“用户打开 App，选择模型并开始聊天”为例，主链路可以简化为：

```text
MainActivity / ModelManagerActivity
    -> HarnessFacade
        -> HarnessModelRegistry
        -> LlamaModelStore
        -> LlamaDownloadManager
        -> LlamaBackendAdapter
            -> LlamaEngine
                -> JNI
                    -> llama.cpp-omni
```

如果是下载模型，则主要是：

```text
ModelManagerActivity
    -> HarnessFacade
        -> ModelDownloadService
            -> LlamaDownloadManager
                -> LlamaEngine.downloadModels(...)
```

所以你可以这样理解：

- 当前 Harness 已经接到了“页面入口”这一层
- 模型清单与通用模型 spec 已经有了独立注册表入口
- 模型存储和下载职责已经开始从 `LlamaEngine` 中拆出
- 但核心运行时职责仍主要留在 `LlamaEngine`

## 6. Harness 到底是什么

在这个项目里，Harness 不是新的模型，不是新的 JNI，也不是新的推理引擎。

Harness 更准确的角色是：

- 编排层
- 适配层
- 统一入口层

它的价值是：

- 对上，给 UI 提供统一接口
- 对下，把底层不同模型/不同 backend 包装起来

所以 Harness 解决的不是“模型能不能跑”的问题，而是“模型如何以统一方式接入”的问题。

## 7. 为什么要引入 Harness

因为在没有 Harness 之前，这个项目存在一个很典型的问题：

- 页面层直接摸底层实现
- 模型信息、下载、加载、推理、能力判断混在一起
- 增加一个新模型或新 backend 时，容易改很多地方

举例来说，如果没有 Harness：

- `MainActivity` 直接依赖 `LlamaEngine`
- `ModelManagerActivity` 直接依赖 `LlamaEngine`
- 模型能力判断分散在页面和 runtime 里
- 后续想替换 backend，会先冲击 UI 层

加入 Harness 后，至少先把“页面如何调用能力”统一起来。

## 8. 当前 Harness 已经做了什么

目前这次最小改动里，Harness 已经具备这些能力：

- 统一提供模型注册表与通用模型 spec
- 统一获取当前模型
- 统一获取模型 capability
- 统一判断当前模型文件是否完整
- 统一加载/卸载当前模型
- 统一文本生成入口
- 统一图片预填充和视频预填充入口
- 统一清理上下文
- 统一删除当前模型文件
- 统一启动下载服务
- 统一模型路径、文件存在性与 artifact 名单访问

简单说，**页面主链路已经切到 Harness，阶段二和阶段三都已经开始**。

## 9. 当前 Harness 还没有做什么

这部分非常重要，因为它说明当前 Harness 还只是“最小版”。

目前还没有完成的点包括：

- 还没有独立的 `LlamaRuntime`
- 还没有把 `LlamaEngine` 彻底拆成 store / download / runtime 三部分
- 没有把 Android 依赖和平台无关核心彻底分开
- 没有把 TTS 路径完整并入 Harness
- 没有形成可直接复用的跨平台 SDK API

所以现在的 Harness 还不是“完整 SDK 内核”，而是“阶段一完成、阶段二首轮已落地、阶段三已开始的架构边界”。

## 10. 你可以怎样理解“最小 Harness”

最小 Harness 的思路不是重写一切，而是：

1. 不动底层 Native 行为
2. 不大改现有下载服务
3. 先把 UI 和底层 runtime 隔开
4. 先建立统一接口和统一入口

所以它更像：

- 一层外壳
- 一层网关
- 一个适配器集合的起点

而不是：

- 完整模型平台
- 完整跨平台 SDK
- 全新推理引擎

## 11. 现在项目中“模型能力”是怎么区分的

当前最重要的能力划分是：

- `TEXT`
- `VISION`
- `VIDEO`
- `TTS`

理解方式如下：

- `TEXT`
  - 纯文本模型，只有 GGUF 主文件
- `VISION`
  - 除了 GGUF，还要有 `mmproj`
- `VIDEO`
  - 基于视觉能力再向上，通常要求 runtime 对多帧处理有明确支持
- `TTS`
  - 需要 acoustic artifact，走另一条能力路径

这套划分很关键，因为后面不管接轻量模型还是做 SDK，都应该优先按 capability 管理，而不是按模型名写分支。

## 12. 如果你现在要继续读代码，建议阅读顺序

为了最快建立认知，建议按这个顺序读：

1. [HarnessModelRegistry.kt](../app/src/main/java/com/example/minicpm_v_demo/harness/HarnessModelRegistry.kt)
   - 先看当前模型清单是如何映射成通用 Harness 模型定义的
2. [ModelInfo.kt](../app/src/main/java/com/example/minicpm_v_demo/ModelInfo.kt)
   - 再看兼容层里保留了哪些原始模型元数据
3. [HarnessFacade.kt](../app/src/main/java/com/example/minicpm_v_demo/harness/HarnessFacade.kt)
   - 看页面现在通过什么入口访问能力
4. [MainActivity.kt](../app/src/main/java/com/example/minicpm_v_demo/MainActivity.kt)
   - 看聊天主链路
5. [ModelManagerActivity.kt](../app/src/main/java/com/example/minicpm_v_demo/ModelManagerActivity.kt)
   - 看模型下载、加载、切换主链路
6. [LlamaEngine.kt](../app/src/main/java/com/example/minicpm_v_demo/LlamaEngine.kt)
   - 看当前实际运行时逻辑集中在哪里
7. [llama_jni.cpp](../app/src/main/cpp/llama_jni.cpp)
   - 最后再看 native 细节

这个顺序比一开始就冲进 JNI 更容易建立全局认知。

## 13. 如果你现在想理解“轻量模型怎么接”

你可以先记住一个最简单的判断：

- 只需要 GGUF 的 text-only 模型，是当前最容易接入的一类

原因：

- 不需要 `mmproj`
- 不需要图片/视频能力
- 不需要 TTS bundle
- 只要底层 GGUF 能加载，就可以先走当前 Harness 主链路

所以后续扩轻量模型时，最先该做的不是改 JNI，而是：

- 增强模型注册
- 增强 capability 管理
- 增强 artifact 清单驱动
- 增强 runtime hints

## 14. 如果你现在想理解“为什么还不能直接叫 SDK”

因为真正的 SDK 通常要求：

- 平台无关核心
- 稳定 API
- 独立模型 manifest
- 可切换 backend
- 会话管理机制
- 可观测性
- 对 Unity / Unreal / iOS / Android 等平台友好

而当前项目虽然已经有 Harness 雏形，但还明显依赖：

- Android Activity
- Android 文件目录
- Android 下载服务
- 现有 `LlamaEngine`

所以现在更准确的说法是：

- 它已经有了 SDK 化方向的架构起点
- 但还没有演进成真正可复用的跨平台 LLM SDK

## 15. 当前最值得记住的结论

如果只记 5 点，记下面这些就够了：

1. 这个项目是 Android UI + Kotlin 编排 + JNI + 本地推理 runtime 的组合工程。
2. `LlamaEngine` 当前是最核心但也最重耦合的类。
3. Harness 在这里不是推理引擎，而是编排层/适配层。
4. 当前 Harness 已经把聊天页和模型管理页的主入口统一起来，并开始拆出模型存储与下载职责。
5. 后续不管是接轻量模型，还是做跨平台游戏 LLM SDK，方向都应该是继续增强 Harness，而不是继续让页面直接依赖底层 runtime。

## 16. 推荐继续阅读的文档

如果你理解完这份快速说明，下一步建议看下面两份：

- [Inte_Harness.md](Harness/Inte_Harness.md)
  - 解释当前为什么这样接入 Harness，以及后续分阶段改造思路
- [Lightweight_Model_SDK_Roadmap.md](Harness/Lightweight_Model_SDK_Roadmap.md)
  - 解释轻量模型接入路径和跨平台游戏 LLM SDK 的演进路线

## 17. 这份文档的最终定位

你可以把这份文档当作：

- 项目结构总览
- Harness 角色说明
- 当前状态说明
- 后续演进的阅读入口

如果以后你要继续推进这个项目，最实用的方式是：

- 先用这份文档建立总览
- 再看 Harness 方案文档
- 最后再进入具体代码或下一阶段实现
