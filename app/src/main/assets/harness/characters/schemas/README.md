# 数据结构

| 文件 | 校验对象 |
| --- | --- |
| `npc_schema.json` | `characters/*.json` Character Card |
| `story_event_schema.json` | `story/story_events.jsonl` 中的单条事件 |

Schema 用于保证字段存在、类型正确，并约束 ID、关系、知识范围和证据引用格式。

运行校验：

```powershell
python scripts\validate_character_data.py
```
