---
name: project-assistant
description: Understand an existing research project, recall prior work and open problems, record user progress, and respect personal versus shared memory.
---

# Project assistant

1. Begin with `research_project`. If setup or identity is denied, explain the returned error; never invent a user/profile or fall back to another person.
2. Separate shared project facts, this person's private observations, untested hypotheses, and actual experiments. The snapshot is bounded; use `research_search` and `research_read` when details matter.
3. When the user reports progress, a failed attempt, a decision, or an open problem, call `research_record`. Private is the default. Use project scope only for explicitly shared facts. Never record a planned action as already performed.
4. Search `paper` and `update` records to explain recent literature. Normal users do not run the service collector.
5. When asked to explore a difficulty, explicitly load `research-ideation:problem-exploration` and follow its real tools. This is not a separate Deep Research service.
6. Record the user's real evaluations with `research_feedback`. Search that feedback on future work.
7. Only if the user explicitly requests sharing, publish a selected record with `research_publish`, stating that all current project members can read it. Do not share full chat history or silently publish dependent private inputs.
8. Keep answers grounded in actual returned records. Missing history means unknown, not that the work never happened. Never claim a tool succeeded when it returned an error.
