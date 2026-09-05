# 剧情事件

`story_events.jsonl` 是所有 NPC 共用的剧情事实库，每行是一条 JSON 事件。

事件的主要字段：

| 字段 | 作用 |
| --- | --- |
| `event_id` | 稳定事件标识，也用于剧情截止点比较 |
| `time_index` | 用于排序和 cutoff 判断的时间序号 |
| `fact` | 提供给模型的剧情事实 |
| `participants` | 事件涉及的角色 |
| `witnesses` / `informed_characters` | 目击或被告知该事件的角色 |
| `visibility` | 可以获知该事件的角色 |
| `keywords` | 检索关键词 |
| `knowledge_by_character` | 各角色的信息来源与置信度 |

事件分组：

- `evt-001`–`evt-020`：原始主剧情事件；
- `evt-021`–`evt-028`：新增角色所需的补充证据切片。

事件 ID 主要服务于稳定引用和知识边界，不应直接解释为原著章节顺序。数据结构由 `../schemas/story_event_schema.json` 约束。
