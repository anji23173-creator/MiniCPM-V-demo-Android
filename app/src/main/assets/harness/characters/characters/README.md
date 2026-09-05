# 角色档案

本目录保存 NPC 的 Character Card。每个 JSON 文件对应一个角色，文件名与 `npc_id` 保持一致。

| 文件 | 角色 | 类型 | 剧情截止点 |
| --- | --- | --- | --- |
| `lu_jiangxian.json` | 陆江仙 | 谨慎布局型 | `evt-018` |
| `xuan_an.json` | 玄谙 | 同源对立型 | `evt-018` |
| `bai_junyi.json` | 白君意 | 妖王决策型 | `evt-024` |
| `qing_yudian.json` | 青谕遣 | 势力执行型 | `evt-024` |
| `jiang_qing.json` | 蒋清 | 遗局谋划型 | `evt-028` |
| `li_jiangqun.json` | 李江群 | 牺牲布局型 | `evt-028` |

统一字段由 `../schemas/npc_schema.json` 定义，主要包括身份核心、关系、知识边界、动态状态、情节记忆和证据引用。

新增或修改角色后运行：

```powershell
python scripts\validate_character_data.py
python -m unittest discover -s tests -v
```
