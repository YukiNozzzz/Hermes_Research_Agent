# MVP 使用说明

当前实现：按 profile 的个人 / 项目记忆、权限检查、arXiv 更新、真实 Hermes 问题探索与结果保存、反馈、明确发布 / 撤回。
微信只提供绑定和路由规划接口，实际消息入口默认关闭。没有独立 Deep Research。

## 已配置的研究项目

- 项目 ID：persona-preference。
- 方向：人设对话领域如何对齐用户偏好。
- 更新：每天 10:00，Asia/Shanghai。
- 历史实验、个人经验、资源限制和数据集尚未提供，系统不会编造。

本机管理员配置在 E:\harness\research-data\control\runtime.json。
它保存真实 Hermes root、Python 和源码位置，不含 API Key。业务数据不保存在插件源码中。

## Windows 入口

```powershell
cd E:\harness\research-ideation
.\run.ps1 -Profile research-alice
# 在另一个终端切换另一个验收用户
.\run.ps1 -Profile research-bob
```

research-alice / research-bob 是功能验收身份，不是已经绑定的真实微信用户。本机这两个 profile 已配置现有网关并通过真实模型调用；凭据只保存在各自 profile 的私有配置中。
以后新增 profile 时需要配置模型网关；管理员工具不会自动克隆他人的 .env。
启动后明确输入：

> 加载 research-ideation:project-assistant，看看 persona-preference 项目当前的目标、已做工作和未解决问题。

> 这是我的个人经验，请只记录为私有：……

> 针对角色设定与用户偏好冲突的问题，加载 research-ideation:problem-exploration，结合已有资料提出一个可验证的方案，并保存研究结果。

> 我试过刚才的方案，结果是……。请把这个反馈关联到对应 idea。

> 请将这条我自己的记录分享给整个项目。

共享资料引用私有来源时会被拒绝；需要先处理来源授权，或用共享材料重新研究。

## 管理与检查

```powershell
.\run.ps1 -Mode tests
.\run.ps1 -Mode admin -Arguments @('doctor','--profile','research-alice')
.\run.ps1 -Mode admin -Arguments @('snapshot','--profile','research-bob','--project','persona-preference')
.\run.ps1 -Mode admin -Arguments @('update','--profile','research-service','--project','persona-preference')
.\run.ps1 -Mode admin -Arguments @('schedule','--profile','research-service','--project','persona-preference')
```

本机默认 minted hermes.exe 在 Codex 环境报依赖锁缺失时，run.ps1 可显式使用已配置的可用 runtime/source。
该方式不跳过依赖校验、不改变全局 sticky profile。Hermes 更新导致路径失效时需管理员更新 runtime.json。

本机已有运行中的 Hermes gateway。每日任务已启用，下一次计划运行时间为 2026-10-27 10:00（Asia/Shanghai）；同一脚本还通过了一次独立的自动定时触发验收。每天执行仍依赖服务器或本机保持 Hermes scheduler/gateway 运行。
默认项目抓取是 no-agent 脚本，不调用模型；用户主动探索才调用模型。完整验收结果见 [VALIDATION.md](VALIDATION.md)。

## 文件在哪里

- 源码：E:\harness\research-ideation。
- 共享项目记录：数据根目录下 projects/persona-preference。
- 个人记录：对应真实 profile 下 plugin-data/research-ideation/records.sqlite。
- 个人研究报告：该 profile 下 plugin-data/research-ideation/reports/<task_id>。
- 模型验收原始记录：对应 profile 下 plugin-data/research-ideation/acceptance，仅保存在所属 profile。
- 用户映射、成员关系：数据根目录下 control/registry.sqlite，只由管理员 CLI 修改。

## Linux 与未来微信

完整部署步骤见 deploy/README.md。迁移源码和需要保留的数据，重新配置真实 profile 路径，不能复制 Windows Python 环境。
聊天接入前必须完成可信账号绑定、宿主命令限制、接入元数据认证和真实错发测试；当前不能直接向不可信聊天用户开放宿主权限。

## 研发文档

- IMPLEMENTATION_PLAN.md：实施目标与验收标准；其中未完成项不会因源码存在而自动通过。
- PROJECT_STRUCTURE.md：各文件职责。
- tests/test_security_and_workflow.py：权限、撤销、并发、证据与幂等的回归测试。
- scripts/live_acceptance.py：显式调用真实模型的验收，需指定已获准使用的凭据文件，会产生模型调用费用。
