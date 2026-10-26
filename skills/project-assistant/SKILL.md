---
name: project-assistant
description: Understand an existing research project, recall prior work and open problems, record user progress, and respect personal versus shared memory.
---

# Project assistant

1. Begin with `research_project`; omit project_id to use the single user's configured default project. If setup or identity is denied, explain the returned error; never invent an identity or fall back to a historical test profile.
2. Separate shared project facts, this person's private observations, untested hypotheses, and actual experiments. The snapshot is bounded; use `research_search` and `research_read` when details matter.
3. When the user reports progress, a failed attempt, a decision, or an open problem, call `research_record`. Private is the default. Use project scope only for explicitly shared facts. Never record a planned action as already performed.
4. Search `paper` and `update` records to explain recent literature. When the user explicitly requests fresh collection, call `research_update_papers`; the selected single user may run it directly. Do not fetch on every ordinary conversation.
5. When asked to explore a difficulty, explicitly load `research-ideation:problem-exploration` and follow its real tools. This is not a separate Deep Research service.
6. Record the user's real evaluations with `research_feedback`. Search that feedback on future work.
7. Only if the user explicitly requests sharing, publish a selected record with `research_publish`, stating that all current project members can read it. Do not share full chat history or silently publish dependent private inputs.
8. Keep answers grounded in actual returned records. Missing history means unknown, not that the work never happened. Never claim a tool succeeded when it returned an error.

## 共享上下文与审核

- `cra:` 编号来自已绑定项目的 CRA PostgreSQL；用实际返回的编号与版本继续读取，不去掉前缀。
- status 与 visibility 独立。草稿可以用于讨论和整理，不能作为已确认研究事实。已采集论文仍是原始资料，尊重摘要 / 全文覆盖范围。
- 经验、决定、实验可补结构化 fields 和 sources；结论、采纳与理由等人工判断字段交给本机管理员 review，不自行填写或冒充确认人。
- 明确发布结构化方案后，若返回 shared_context，说明其已作为 PostgreSQL draft 保存；这不表示人已采纳。私有输入依赖不允许自动分享。
- 数据库连接失败是失败，不等于没有历史。不要用其他用户 profile、路径或 SQL 绕过工具。
