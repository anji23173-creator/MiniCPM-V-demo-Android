# Harness 改动记录

## 本次修改目标

本文记录 Harness 相关改动的当前状态。截止 2026 年 7 月 17 日，项目已经完成 Harness 接入的阶段一，完成阶段二的首轮职责拆分，并落地阶段三的模型注册表入口。

最初目标是在不重写现有 `LlamaEngine + JNI + llama.cpp-omni` 链路的前提下，以最小改动方式把 Harness 接入当前项目，使其先承担统一编排层/适配层角色。

## 实际修改内容

### 1. 阶段一：新增 Harness 抽象层

新增目录：

- `app/src/main/java/com/example/minicpm_v_demo/harness/`

新增文件：

- `HarnessModelSpec.kt`
  - 定义最小模型抽象：`HarnessModelSpec`、`HarnessArtifact`、`HarnessCapability`
  - 提供 `ModelInfo.toHarnessSpec()` 映射
- `HarnessBackend.kt`
  - 定义最小后端接口
- `LlamaBackendAdapter.kt`
  - 把现有 `LlamaEngine` 封装为 Harness backend
- `HarnessFacade.kt`
  - 对 Activity 提供统一入口

### 2. 阶段一：Activity 层切换到 HarnessFacade

修改文件：

- `app/src/main/java/com/example/minicpm_v_demo/MainActivity.kt`
- `app/src/main/java/com/example/minicpm_v_demo/ModelManagerActivity.kt`

改动方式：

- 原先直接依赖 `LlamaEngine` 的主流程，改为依赖 `HarnessFacade`
- 保留现有 `LlamaState` 状态流，避免一次性大改 UI 状态机
- 模型加载、卸载、会话清理、图片预填充、视频预填充、文本生成、模型删除、模型切换等动作，统一从 Harness 层进入

### 3. 阶段一：文档结构调整

新增目录：

- `docs/Harness/`

文档归档：

- `Inte_Harness.md` 已移动到 `docs/Harness/Inte_Harness.md`
- 本文档新增为 `docs/Harness/Mini_Change.md`

### 4. 阶段二：已开始拆分的职责

新增文件：

- `LlamaModelStore.kt`
  - 负责当前模型选择、路径、文件存在性判断、artifact 名单、删除与切换标记
- `LlamaDownloadManager.kt`
  - 负责下载执行入口以及前台下载服务适配

对应调整：

- `HarnessFacade.kt`
  - 改为委托 `LlamaModelStore` 和 `LlamaDownloadManager`
- `ModelDownloadService.kt`
  - 不再直接调用 `LlamaEngine.downloadModels(...)`
  - 改为通过 `LlamaDownloadManager` 执行下载

### 5. 阶段三：模型定义泛化已开始落地

新增文件：

- `HarnessModelRegistry.kt`
  - 作为当前模型清单与 Harness 通用 spec 的统一入口

已完成的阶段三内容：

- `HarnessModelSpec` 已扩展为通用模型结构，包含：
  - `family`
  - `artifacts`
  - `downloadSources`
  - `runtimeHints`
- `ModelInfo.toHarnessSpec()` 不再只是最小映射，而是会生成更完整的通用 spec
- `ModelManagerActivity.kt` 已开始通过 `HarnessModelRegistry` 暴露的模型列表工作
- `LlamaModelStore.kt` 已改为按 registry + artifact 列表判断模型文件完整性
- `LlamaEngine.getSelectedModel(...)` 已开始通过 `HarnessModelRegistry` 做模型 ID 解析

## 当前刻意没有修改的部分

为了保持风险可控，当前仍然没有改以下部分：

- `LlamaEngine.kt` 的核心实现逻辑
- `ModelDownloadService.kt` 的前台服务实现
- `llama_jni.cpp`
- `CMakeLists.txt`
- `TtsActivity.kt` / `TtsEngine.kt`

说明：

- TTS 仍然沿用当前项目的原路径
- 下载服务仍然复用原有前台服务形态，只是下载执行入口开始由 Harness 层承接
- Native 推理链路不变，因此本次风险主要集中在 Kotlin 层边界调整

## 最终效果

### 代码结构上的效果

- UI 层不再直接依赖 `LlamaEngine` 作为主调用入口
- 当前本地 llama backend 被包装成 `LlamaBackendAdapter`
- 项目里已经形成 Harness 外壳，并开始把模型存储与下载职责从 `LlamaEngine` 拆出

### App 使用层面的体现

用户界面本身不会新增一个叫 “Harness” 的功能入口，但会有这些结构性变化：

- 聊天页和模型管理页开始共享同一层编排入口
- 模型切换、加载、会话生成、图片预填充等动作不再各自直连底层实现
- 后续如果替换 backend 或增加新模型运行时，优先改 Harness 层，不必先改页面逻辑

### 当前 Harness 已覆盖的能力

- 统一获取当前模型与模型能力
- 统一判断模型文件是否完整
- 统一加载/卸载当前模型
- 统一发起文本生成
- 统一清理上下文
- 统一图片/视频预填充
- 统一删除当前模型文件
- 统一启动模型下载服务
- 统一模型路径、文件存在性与 artifact 名单访问

## 验证结果

已执行：

```bash
./gradlew :app:compileDebugKotlin
```

结果：

- 编译成功

备注：

- 首次在受限环境下执行时，因为 `~/.gradle` 锁文件访问受限失败
- 在授权访问 `~/.gradle` 后，编译检查通过

## 结论

当前修改完成的是“阶段一已完成、阶段二首轮已落地、阶段三已开始”的 Harness 接入，不是“完整 SDK 化重构”。

当前项目已经具备：

- Harness 抽象入口
- Llama backend 适配器
- Activity 对 Harness 的主链路切换
- 独立的模型存储职责入口
- 独立的下载职责入口
- 独立的模型注册表入口
- 通用的 Harness 模型 spec 结构

后续如果继续演进，建议下一步优先做：

1. 把 `LlamaEngine` 中的运行时职责继续拆分为独立 `LlamaRuntime`
2. 继续把 UI / 下载 / 运行时对 registry 的使用彻底统一
3. 把 TTS 路径也逐步并入 Harness 能力模型
