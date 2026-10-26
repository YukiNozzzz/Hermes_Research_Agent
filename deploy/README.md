# 部署与边界

使用已有 Hermes，不另建实验 HERMES_HOME。用户 profile 是多用户运行载体，不能当作操作系统沙箱。

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
- 当前插件对非 CLI 的原生消息入口返回 CHANNEL_NOT_CERTIFIED；已提供账号映射、路由预览和交付校验接口，但没有假装完成真实微信身份验证。
- 真正开放聊天软件前要接通经过验证的原生 ingress 元数据，并完成命令门禁、默认 profile、/new、并发与错发验收。
- 不直接把包含所有 profile 的 HTTP / 桌面管理接口暴露给普通用户。
- 管理员 / 同一 OS 账号直接操作文件不在应用级隔离承诺内。恶意多租户要求额外的执行资源隔离。

## Windows 路径注意

Codex MSIX 的 AppData 虚拟化可能使正常 AppData 路径与实际 profile 路径不同。
control/runtime.json 必须使用解析后的真实 Hermes root；run.ps1 会显式使用该 root，不更改全局 sticky profile。
若默认 hermes.exe 环境损坏，可在 runtime.json 配置已有可用 Hermes 的 python/source。
HermesCommand 使用官方 HERMES_PYTHON_SRC_ROOT 指向对应源码，不关闭 PM 校验或伪造启用状态。

## 必要检查

```bash
python -m unittest discover -s tests -v
python -m research_ideation.admin --data-root /srv/research-data doctor --profile research-alice
python -m research_ideation.admin --data-root /srv/research-data snapshot --profile research-bob --project persona-preference
```

自动测试使用临时业务记录验证权限与并发，不创建额外的 Hermes 运行环境。
模型生成不是单元测试；真实验收需要检查保存的任务、实际证据、候选和报告，而不只看模型最终回答。
