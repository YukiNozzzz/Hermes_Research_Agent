# 内部使用的两种运行身份

从 0.3.0 起，只保留 user（可信内部用户）与 service（后台 cron 服务）。每个内部用户仍有独立 Hermes profile、原生会话和个人工作状态。同项目内部成员权限相同，不再区分 owner / editor / reader。

## 能力

| 身份 | 工具暴露 | 项目业务权限 |
| --- | --- | --- |
| user | hermes-cli 原生交互工具 + research_ideation + skills，保留额外自定义工具集 | 同项目共享记录的读写、审核、发布与撤回；研究工具默认只读写本人的私有区 |
| service | research_ideation + skills | 项目论文采集与后台流程；不访问私有区，不执行人工审核或远程撤回 |

hermes-cli 恢复终端、文件、代码、检索、技能等 Hermes 原生常用能力；工具仍受 Hermes 的可用性、凭据、平台和原生操作审批机制约束，不自动连接第三方服务，也不授予系统 root 或数据库超级用户权限。全局 agent.disabled_toolsets 会覆盖工具集配置，所以权限升级会清空这一旧抑制列表。

内部用户恢复 profile 自身的原生个人记忆，不再强制 creation_nudge_interval=0；保留其他自定义 Skill 设置，不批量安装或复制其他人的私人 Skill。新建普通 profile 不再传 --no-skills，服务 profile 保留该选项。升级现有 profile 不复制默认 profile 的会话、凭据或技能目录。原有模型、密钥引用、额外插件设置和额外工具集保持，后台付费审查不会自动开启。服务端按照原生规则发现插件注册的两个研究 Skill。

## 新建

```bash
python -m research_ideation.admin --data-root /srv/research-data user-add --id alice --profile research-alice
python -m research_ideation.admin --data-root /srv/research-data user-add --id paper-service --profile research-service --service
python -m research_ideation.admin --data-root /srv/research-data member --project persona-preference --user alice
python -m research_ideation.admin --data-root /srv/research-data member --project persona-preference --user paper-service
```

member 默认按已登记的身份设置成员类型，也可显式传 --role user 或 --role service。为兼容旧脚本，--role owner / editor / reader 会映射为 user，不再提供不同权限。已有 SQLite 表结构不变，旧角色在每次成员读取时兼容解释为 user；身份与成员类型冲突仍报错。

## 升级已有 profile

先预览，再应用：

```bash
python -m research_ideation.admin --data-root /srv/research-data permissions-sync --all
python -m research_ideation.admin --data-root /srv/research-data permissions-sync --all --apply
```

可用 --profile research-alice 代替 --all，仅升级一个已登记、已启用的 profile。应用时逐个在 profile 内保存 config.yaml.permissions-backup-*，原子替换配置，并把该用户已有成员登记中的旧角色写成 user；已是目标配置时不重复备份。默认预览不写配置或业务数据。备份可能包含私人模型配置，不放进源码仓库。批量应用按 profile 执行，不是跨文件事务；某项失败时已成功项保留，修复后重跑即可。

重复执行相同 user-add 也会为已登记的同一身份同步策略；不会把已有 user 改成 service。停用状态和成员撤销不被升级恢复。配置变化后开启新会话；已冻结的工具列表不会在原会话内自动扩展。升级不启动新任务或重启 gateway。

随后运行 doctor。它按 user / service 分别校验，不再因为内部用户具有文件、终端或个人记忆能力而报错；服务 profile 意外暴露其他工具集仍报异常。

## 信任与数据边界

这是可信内部团队的使用模型。完整工具能访问系统账号允许的文件，所以 profile 不是磁盘沙箱，不能承诺不同内部用户之间强隔离。研究工具仍保留本人私有记录过滤、项目成员检查、停用 / 撤销检查、私有来源不可直接公开等边界，减少误操作；这些业务检查不约束用户授权的任意代码执行。

PostgreSQL 的既有项目绑定、草稿 / 确认流程、来源和版本检查继续生效。同项目 user 可管理共同资料，包括其他成员发布的内容。人工字段通过本机 review 入口处理，后台服务不作为人工确认身份。此变更未修改 PostgreSQL 账号、GRANT、RLS 或数据库超级用户权限；严格数据隔离与数据库授权需要另外部署。

未来聊天软件的可信身份认证仍待实现，当前研究工具的非 CLI 入口仍拒绝；开放内部用户工具不等于已经开放微信或其他外部入口。
