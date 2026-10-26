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
9. For service cron runs, first call `research_update_papers`. Only when its auto_explore flag is true AND new_count > 0, select a relevant shared problem from `research_project` and run the same workflow. Do not use a user's private history or start unlimited follow-up tasks. If there is no shared problem, just report the update and stop.
