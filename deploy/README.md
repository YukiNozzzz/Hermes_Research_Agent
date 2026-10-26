# 部署与边界

使用已有 Hermes，不另建实验 HERMES_HOME。用户 profile 是多用户运行载体，不能当作操作系统沙箱。

## 上传什么

用 Git 推送本仓库源码即可，保留 plugin.yaml、根注册入口、schemas.py、tools.py、research_ideation/、skills/ 和 pyproject.toml。仓库已移除测试和验收脚本，日常操作与部署步骤在保留的四份文档中说明。

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
python -m research_ideation.admin --data-root /srv/research-data member --project persona-preference --user alice --role owner
python -m research_ideation.admin --data-root /srv/research-data member --project persona-preference --user bob --role editor
python -m research_ideation.admin --data-root /srv/research-data member --project persona-preference --user paper-service --role service
```

管理员命令会调用 Hermes 原生创建和启用机制。依赖准备期间不要修改插件源码；Hermes 会拒绝输入发生变化的发布，可用 --resume 重试本次受控安装。
请在个人 profile 中配置模型；不从另一个用户 profile 克隆会话、记忆或整个 .env。
Windows 用 junction，Linux 用目录符号链接，将同一源码接入各 profile。数据目录禁止通过链接越出受控范围。

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
默认研究能力仅 research_ideation、skills，原生长期记忆写回关闭，聊天仍保留在原生 profile。
模型需要配置在各 profile；collect-only 的服务 cron 不需要模型凭据。
开启 auto-explore 时，需把已有任务明确配置为带 Skill 的 Agent 任务，同时配置服务模型；不会偷偷将 collect-only 任务变成付费模型任务。

## 多用户隔离

- 注册表只由管理员 CLI 修改；普通用户不获得服务器 shell 或任意 profile 选择权限。
- 未注册 / 禁用 / 不匹配的 profile 无法调用研究操作。每次访问重新检查成员关系。
- Profile 自身不提供磁盘隔离；研究工具白名单之外的原生终端、代码、任意文件、插件管理等能力必须限制。
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

config.example.yaml 默认给出 Linux /srv/research-data，仅供合并参考；user-add 已为新 profile 写入管理员命令实际使用的数据位置，不能在事后用示例覆盖。

## 必要检查

```bash
python -m research_ideation.admin --data-root /srv/research-data doctor --profile research-alice
python -m research_ideation.admin --data-root /srv/research-data snapshot --profile research-bob --project persona-preference
```

实际使用时还需检查保存的任务、证据、候选和报告，不能只看模型最终回答。
