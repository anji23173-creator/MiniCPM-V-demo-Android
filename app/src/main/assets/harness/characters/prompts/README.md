# Prompt 模板

| 文件 | 用途 |
| --- | --- |
| `roleplay_system.prompt` | 角色扮演系统 Prompt，定义证据优先级、输出约束与拒答边界 |
| `character_extraction.prompt` | 从原始剧情材料提取结构化角色信息 |

运行时由 `runtime/prompt_compiler.py` 加载模板，并注入 Character Card、可知事件、情节记忆、会话状态和当前问题。

修改模板后建议运行全部测试，并用以下命令检查实际编译结果：

```powershell
python scripts\presentation_demo.py prompt --npc lu_jiangxian --question "你是谁？"
```
