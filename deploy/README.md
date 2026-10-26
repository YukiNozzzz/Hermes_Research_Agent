# 部署与边界

使用已有 Hermes，不另建实验 HERMES_HOME。用户 profile 是多用户运行载体，不能当作操作系统沙箱。

0.3.0 面向可信内部团队，只分 user / service：内部用户使用完整原生常用工具，后台 cron 服务受限。同项目内部成员权限相同。完整配置和已有 profile 升级见 [权限说明](../PERMISSIONS.md)。

## 上传什么

用 Git 推送本仓库源码即可，保留 plugin.yaml、根注册入口、schemas.py、tools.py、research_ideation/、skills/ 和 pyproject.toml。仓库已移除测试和验收脚本，日常操作、权限升级与部署步骤分别见使用说明和部署文档。

缓存、虚拟环境、密钥、本机运行配置和数据库不放进 Git。Windows 的 run.ps1 是本机入口，Linux 直接执行下文 Python / Hermes 命令。

本仓库的控制、私有和运行数据保留 SQLite；0.2.0 可通过管理员 shared-bind 接入 CRA PostgreSQL 的共同项目资料，并显式导出方案草稿。两套记录通过统一存储入口和审核状态衔接，公共 PostgreSQL 仍只绑定一个项目。Linux 上需要另外配置 CRA 的仓库、Python 和 .env 路径，详见 [对齐说明](../ALIGNMENT.md)。

## Linux 首次测试

建议先在服务器创建空白测试数据，不直接复用 Windows 注册表。以下数据位置为 /srv/research-data，Hermes 根目录以 ~/.hermes 为例；请替换为服务器真实位置，并确保当前账号有写权限。

先按服务器已安装 Hermes 的实际配置找到可用 Python，在仓库根目录执行：

```bash
research_python="/absolute/path/to/the/existing/hermes/python"
"$research_python" -c 'import hermes_cli.main'
```

第一条导入检查失败时，先确认 Hermes 的 Python / 源码环境，不用系统 Python 代替。不要复制 Windows 虚拟环境。若使用需要指定源码的安装，可以在下文 init 追加 --hermes-source /实际/Hermes/源码路径，并确保测试命令也在匹配的环境中运行。

确认可用后，按下一节初始化。将所有示例中的 python 换为 `"$research_python"`，init 时同时添加 `--hermes-python "$research_python"`，让原生 cron 使用相同解释器。模块命令从本仓库根目录运行；插件以符号链接指向源码，部署后保留这一目录，更新时使用原位置 git pull。

首次测试顺序：初始化 → 创建项目和 profile → 设置成员 → 配置用户模型 → doctor → 手动更新论文 → 查询概览 → 新会话中探索。手动流程通过之后，再执行 schedule 启用每日任务。user-add 会创建并启用插件，不要把服务器已有的同名个人 profile 当作空白测试 profile；有名称冲突时改用未占用的名字，并同步修改后续示例。

## 初始化

在 Hermes 的 Python 环境中，从插件根目录运行：

```bash
python -m research_ideation.admin --data-root /srv/research-data init --hermes-root ~/.hermes
python -m research_ideation.admin --data-root /srv/research-data project-add --id persona-preference --title '人设对话领域如何对齐用户偏好' --brief '研究人设对话领域如何对齐用户偏好；历史实验与资源约束待补充。' --query 'cat:cs.CL AND (all:persona OR all:roleplay OR all:role-playing) AND (all:preference OR all:alignment OR all:personalization)' --time 10:00 --timezone Asia/Shanghai
python -m research_ideation.admin --data-root /srv/research-data user-add --id alice --profile research-alice
python -m research_ideation.admin --data-root /srv/research-data user-add --id bob --profile research-bob
python -m research_ideation.admin --data-root /srv/research-data user-add --id paper-service --profile research-service --service
python -m research_ideation.admin --data-root /srv/research-data member --project persona-preference --user alice
python -m research_ideation.admin --data-root /srv/research-data member --project persona-preference --user bob
python -m research_ideation.admin --data-root /srv/research-data member --project persona-preference --user paper-service
```

管理员命令会调用 Hermes 原生创建和启用机制。依赖准备期间不要修改插件源码；Hermes 会拒绝输入发生变化的发布，可用 --resume 重试本次受控安装。
请在个人 profile 中配置模型；不从另一个用户 profile 克隆会话、记忆或整个 .env。
Windows 用 junction，Linux 用目录符号链接，将同一源码接入各 profile。数据目录禁止通过链接越出受控范围。

## 已有服务器升级至 0.3.0

先确保 0.3.0 的源码改动已经提交并推送到服务器使用的远程分支。在服务器仓库目录执行 git pull --ff-only；如提示有未提交改动，先处理自己的改动，不使用强制覆盖。本文的 research_python 仍指服务器真实可用的 Hermes 解释器。

已有部署不重复执行 init、project-add 或 user-add。先备份 data_root/control/registry.sqlite，再预览并应用新策略：

```bash
"$research_python" -m research_ideation.admin --data-root /srv/research-data permissions-sync --all
"$research_python" -m research_ideation.admin --data-root /srv/research-data permissions-sync --all --apply
```

预览阶段不写入。检查结果中的 user 使用 hermes-cli、research_ideation、skills，service 仅使用 research_ideation、skills，再执行 --apply。应用会在各 profile 内备份旧配置，保留模型和其他自定义设置；旧成员角色归并为 user，成员撤销及账号停用保持。已有 cron 不重建，升级命令不重启 gateway、不执行研究任务或模型调用。

升级后检查用户与服务：

```bash
"$research_python" -m research_ideation.admin --data-root /srv/research-data doctor --profile research-alice
"$research_python" -m research_ideation.admin --data-root /srv/research-data doctor --profile research-service
"$research_python" -m research_ideation.admin --data-root /srv/research-data snapshot --profile research-alice --project persona-preference
hermes -p research-service cron list
```

doctor 的 configuration_ok 应为 true，kind 应分别为 user 和 service；插件 doctor 也须通过。有 PostgreSQL 绑定时再运行 shared-check --profile research-alice --project persona-preference（同样使用上述 Python、模块和 data-root 前缀），核对共享数据库连接。工具恢复不依赖重新绑定数据库，也不修改数据库账号、GRANT 或 RLS。

最后退出旧的 Hermes 会话并重新进入，或使用 /new；已冻结的工具列表不会在旧会话中扩展。在内部用户的新会话中验证文件 / 终端等常用能力，服务 profile 应保持受限。若使用长期运行的 gateway，按对应 Hermes 版本确认新会话已重新读取配置；不要重复启动第二个 gateway。

## 实际调度

```bash
python -m research_ideation.admin --data-root /srv/research-data schedule --profile research-service --project persona-preference
hermes -p research-service cron list
```

默认是 no-agent Python 脚本抓取，不消耗模型生成费用。时间解释使用 service profile 的 Asia/Shanghai 设置。
job 创建后还需要 Hermes gateway / scheduler 实际运行。使用当前安装支持的启动方式，不能重复启动冲突的网关。
服务启动与微信接入应按该服务器 Hermes 版本配置；本项目不自动替换现有网关服务。
可用原生 cron run 手动验收脚本；手动执行不等于已经观察到每天 10:00 的定时触发。

## 研究与模型

用户 profile 启动后，明确加载 research-ideation:project-assistant。
问题探索加载 research-ideation:problem-exploration，由 Hermes 调用真实业务操作完成推理与保存。
内部 user 默认使用 hermes-cli + research_ideation + skills，恢复原生个人记忆，可修改代码、操作文件、使用终端和其他可用工具。service 仅保留 research_ideation、skills，关闭个人记忆和后台审查。新建 user 按 Hermes 默认规则继承技能，新建 service 使用 --no-skills；插件自己注册的两个研究 Skill 独立存在。
模型需要配置在各 profile；collect-only 的服务 cron 不需要模型凭据。
开启 auto-explore 时，需把已有任务明确配置为带 Skill 的 Agent 任务，同时配置服务模型；不会偷偷将 collect-only 任务变成付费模型任务。

## 多用户隔离

- 注册表通过本机管理 CLI 修改；可信内部 user 可按任务使用终端、文件等工具，不再作为受限聊天用户运行。
- 未注册 / 禁用 / 不匹配的 profile 无法调用研究操作。每次访问重新检查成员关系。
- Profile 自身不提供磁盘隔离。同系统账号下开放完整工具后，内部用户可能读到其他 profile 文件；严格隔离需另行配置 OS / 容器 / 数据库权限。
- 当前插件对非 CLI 的原生消息入口返回 CHANNEL_NOT_CERTIFIED；已提供账号映射和路由预览，真实微信接入仍待实现。
- 真正开放聊天软件前要接通经过验证的原生 ingress 元数据，并完成命令门禁、默认 profile、/new、并发与错发验收。
- 不直接把包含所有 profile 的 HTTP / 桌面管理接口暴露给普通用户。
- 管理员 / 同一 OS 账号直接操作文件不在应用级隔离承诺内。恶意多租户要求额外的执行资源隔离。

## Windows 路径注意

Codex MSIX 的 AppData 虚拟化可能使正常 AppData 路径与实际 profile 路径不同。
control/runtime.json 必须使用解析后的真实 Hermes root；run.ps1 会显式使用该 root，不更改全局 sticky profile。
若默认 hermes.exe 环境损坏，可在 runtime.json 配置已有可用 Hermes 的 python/source。
HermesCommand 使用官方 HERMES_PYTHON_SRC_ROOT 指向对应源码，不关闭 PM 校验或伪造启用状态。

Windows 验收报告里的 profile 名称、任务 ID、下次调度时间和 E: / C: 路径只描述当时本机状态，不是服务器部署结果。不要将本机 control/runtime.json 或整份 registry.sqlite 直接当作 Linux 配置：前者保存解释器 / 源码路径，后者保存 profile 绝对路径和本机调度 job_id。新服务器重新初始化、登记用户和创建调度；首次空白测试不迁移本机研究数据。需要迁移历史时，另外安排数据库一致性备份、私有目录迁移、身份路径重绑定及来源 / 权限回归，不在本次清理中自动执行。

config.example.yaml 是内部 user 示例，config.service.example.yaml 是后台服务示例，均默认给出 Linux /srv/research-data，仅供合并参考；user-add 已写入管理员命令实际使用的数据位置，不能在事后用示例覆盖。

## 必要检查

```bash
python -m research_ideation.admin --data-root /srv/research-data doctor --profile research-alice
python -m research_ideation.admin --data-root /srv/research-data snapshot --profile research-bob --project persona-preference
```

实际使用时还需检查保存的任务、证据、候选和报告，不能只看模型最终回答。
