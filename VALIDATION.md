# 本机 MVP 验收记录

验收日期：2026-10-26。结论：Windows CLI 流程已跑通，Linux 服务器尚未部署，微信尚未接入。

机器可读结果：[summary.json](../research-data/acceptance/summary.json)。该文件只记录通过状态与产物标识，不含模型密钥或私人对话正文。

## 已完成

| 项目 | 实际结果 |
| --- | --- |
| 插件注册 | Hermes 原生 doctor 通过，9 个工具、2 份 bundled Skill |
| 真实运行身份 | research-alice、research-bob、research-service 已创建并启用插件，源码通过 junction 接入 |
| 研究项目 | persona-preference：人设对话领域如何对齐用户偏好 |
| arXiv | 真实保存 10 篇相关论文的元数据和摘要，记录抓取上限与可能截断；不是宣称当天新发表了 10 篇 |
| 模型探索 | Alice 通过真实网关完成检索、阅读、生成和保存，产生 1 个私有候选 idea，7 条可回查的证据引用 |
| 多用户读取 | Bob 真实模型能读取共享概况，未读到 Alice 的私有验收标记与候选 idea；直接猜测私有记录 ID 也被拒绝 |
| 自动化回归 | 20 项测试通过：身份、成员撤销、分享 / 撤回、历史证据、并发、幂等、来源失败等 |
| 并发首次打开 | 修复数据库首次初始化锁竞争后，额外重复 12 次并发用例均通过 |
| 每日调度 | 原生任务 64da4cd7fa7b 已启用，每天 10:00、Asia/Shanghai；手动补跑成功 |
| 自动定时触发 | 独立的一次性任务 df18ca56d254 于 2026-10-26 14:28:21 +08:00 自动执行成功，完成 1 次后停用 |
| 密钥检查 | 项目源码中未发现本次实际使用的网关密钥 |

每日任务验收时的下一次运行时间为 **2026-10-27 10:00 +08:00**。该时间点尚未到达，因此不是已经观察到每日 10:00 的执行；自动定时任务已验证调度器能启动相同的采集脚本。日常运行要求现有 Hermes gateway / scheduler 持续在线。

## 可回查的产物

- 研究任务：task_7be36c3dc2624d23ae39804096db7da6。
- 私有候选：idea_df19f64d756743f682a7890c0e04c9fb。
- 候选方向：在角色设定与用户偏好冲突时，依据证据充分性选择角色内顺从、角色内协商或出戏澄清，并设计验证实验。
- Alice 研究报告：真实 research-alice profile 下的 plugin-data/research-ideation/reports/上述任务 ID/report.md 和 result.json。
- Alice / Bob 模型验收对话：各自 profile 下 plugin-data/research-ideation/acceptance，原始内容不复制到共享项目目录。
- 共享论文、更新记录和调度验收元数据：E:\harness\research-data。

该候选是基于有限论文摘要得到的待验证假设，不代表已经证明新颖性或实验有效性。尚未提供的历史实验与个人经验未被编造；私有标记记录仅用于隔离验收。

## 使用与边界

入口为 [run.ps1](run.ps1)，示例见 [QUICKSTART.md](QUICKSTART.md)。本机默认 hermes.exe 在 Codex 环境存在依赖定位问题，入口显式使用已验证可用的现有 Hermes Python / source，不修改全局启动器。可用运行时报告为 Hermes v0.22.4；升级后应重新校验插件接口及路径。

Profile 提供原生会话分离，研究插件提供应用层访问检查，不构成操作系统沙箱。普通用户不应得到宿主 shell 或任意 profile 切换权限。当前非 CLI 消息入口默认拒绝，账号绑定、路由规划和收件校验接口不等于已经接通微信。

自动探索默认关闭，每日任务仅采集，不调用模型；独立 Deep Research 未实现。Linux 迁移步骤见 [部署说明](deploy/README.md)，实际服务器部署与聊天渠道接入另行验收。
