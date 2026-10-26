---
name: problem-exploration
description: Explore a specific research difficulty using accessible project history and papers; develop, critique and save evidence-grounded hypotheses and minimal experiments.
---

# Problem exploration

1. Clarify the difficulty only if the goal is missing. Use `research_start(question=...)` and retain its task_id. Start does not generate scientific ideas; you must actually reason about the returned history and evidence.
2. Review prior attempts, constraints and feedback in the task background. Search related papers, problems, experience, experiments and past ideas with `research_search(task_id=...)`. Query alternative method terms, not just the user's exact phrase.
3. Read the important matching records with `research_read(task_id=...)`. Papers may contain abstracts only. Do not describe this as a full-paper reading or exhaustive external search.
4. Form a few distinct hypotheses, then search/read for nearest prior work, counterexamples and past failures. Do not merely combine paper titles. Keep user experience distinct from published findings.
5. Review novelty within the actually checked corpus, plausibility, simpler alternatives, resource limits and what would falsify the hypothesis. One agent's review is not independent validation.
6. Keep at most three candidates, or none. Each must contain exactly title, hypothesis, method, related_work, experiment, risks, refs. Experiments specify a baseline, data, metric and failure criterion. Each reference needs the actual id/version read in this task; optional quote must be verbatim.
7. Call `research_finish` with candidates, review, check_scope and open_questions. State missing sources and abstract-only coverage. If evidence is insufficient, save zero candidates with the reasons instead of inventing citations.
8. Finish returns persistent idea IDs and saved report metadata. Report actual success/error to the user. Retrying finish is safe. Only an explicit sharing request authorizes later publication of personal output.
9. For explicitly configured scheduled ideation runs, first call `research_update_papers`. Only when its auto_explore flag is true AND new_count > 0, select one relevant shared problem from `research_project` and run the same workflow. The selected single user or an existing collector may execute the schedule; do not assume a separate service is required. Keep scheduled output based on shared inputs, do not start unlimited follow-up tasks, and stop after the update if there is no shared problem. The default no-agent collection schedule does not load this workflow.

## 已确认知识与候选草稿

CRA PostgreSQL 记录使用 `cra:` 前缀，和本地记录一起经工具按权限读取。任务背景中的未确认笔记、问题和反馈只提供上下文；实际依据须为 confirmed 知识或明确标注覆盖范围的原始 paper。不得用 draft / rejected / superseded 结论冒充已确认事实。

`research_finish` 保存的 idea 对应 proposal，初始 status 为 draft，默认仍私有。不要填写“已采纳”“实验成功”等人工判断。只有用户明确要求共享后才调用 research_publish；返回的远程草稿编号、状态与研究完成状态要分别说明。引用须保留实际 id/version/quote，先读取全文与来源，再做结论。
