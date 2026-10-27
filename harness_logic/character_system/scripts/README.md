# 脚本说明

所有命令均在项目根目录执行。

## 汇报展示

| 脚本 | 用途 |
| --- | --- |
| `presentation_demo.py` | 离线展示角色、问题、Prompt 和正式实验结果 |
| `run_showcase.py` | 调用真实模型批量运行 36 条 Showcase 并保存 Q&A |
| `generate_character_cards.py report` | 生成角色卡 Markdown 汇总 |
| `compile_prompt.py` | 编译并导出单轮 Prompt |

## 对话与评测

| 脚本 | 用途 |
| --- | --- |
| `chat_agent.py` | 与单个 NPC 进行真实多轮对话 |
| `evaluate_multiturn_qa.py` | 运行 Card Only 与 Card + Memory 多轮对比 |
| `compare_agent_baseline.py` | 早期探索性对比，结果存入归档目录 |
| `run_qa_cases.py` | 批量编译预设问答用例 |

## 数据维护

| 脚本 | 用途 |
| --- | --- |
| `validate_character_data.py` | 校验角色卡、事件与引用 |
| `build_knowledge_base.py` | 从原文、现有数据和可选网页构建角色知识图谱 |
| `export_agent_kb_bundle.py` | 导出给角色 Agent 同事使用的最小知识库接入包 |
| `build_knowledge_base_v2.py` | 构建场景级时序角色认知图谱和 SQLite/FTS5 数据库 |
| `query_knowledge_base_v2.py` | 查询 V2 数据库并查看边界过滤决定 |
| `export_agent_kb_bundle_v2.py` | 导出 V2 Agent 最小接入包 |
| `generate_character_cards.py prepare` | 准备角色卡生成 Prompt |
| `generate_character_cards.py report` | 刷新 `reports/character_cards.md` |

## 《三体Ⅱ：黑暗森林》固定五角色数据

原文默认为 `../three_body_2.txt`（脚本自动识别 GB18030），产物独立写入
`generated/three_body_2/`，不会覆盖原有角色与知识库：

```powershell
python scripts\generate_character_cards.py three-body-2
python scripts\build_knowledge_base_v2.py --three-body-2
```

固定角色为罗辑、章北海、史强、庄颜和丁仪。第二条命令会回填角色卡的事件引用，
并生成兼容现有 `SQLiteKnowledgeStoreV2` 的 SQLite/FTS5 知识库。

常用命令：

```powershell
python scripts\presentation_demo.py
python scripts\build_knowledge_base.py --mode bootstrap
python scripts\run_showcase.py --model your-model-name --limit 2 --no-review
python scripts\validate_character_data.py
python -m unittest discover -s tests -v
```
