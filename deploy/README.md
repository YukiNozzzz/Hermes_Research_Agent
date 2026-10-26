# Linux 单用户部署与升级

当前版本 0.4.0，目标是在一台服务器上先跑通一个人的研究流程。使用已有 Hermes 安装，不需要 Docker，不要求新建个人 Linux 账号，也不强制创建研究专用 profile。

## 准备

把源码放在固定路径，例如 /opt/research-ideation。数据放在独立且当前运行账号可写的位置，例如 /srv/research-data；这只是应用目录，不是 PostgreSQL 数据文件目录。

在源码目录操作，使用实际可用的 Hermes Python：

```bash
research_python="/absolute/path/to/existing/hermes/python"
"$research_python" -c 'import hermes_cli.main'
```

不要复制 Windows 虚拟环境。若安装需要明确源码位置，init 添加 --hermes-source /实际/Hermes源码目录；解释器和源码必须来自同一安装。下文命令中的路径替换为服务器真实值。

## 首次部署

先在原 Hermes 中完成模型配置，然后运行：

```bash
"$research_python" -m research_ideation.admin --data-root /srv/research-data init --hermes-root "$HOME/.hermes" --hermes-python "$research_python"
"$research_python" -m research_ideation.admin --data-root /srv/research-data project-add --id persona-preference --title '人设对话领域如何对齐用户偏好' --brief '研究人设对话领域如何对齐用户偏好；历史实验和资源限制待补充。' --query 'cat:cs.CL AND (all:persona OR all:roleplay OR all:role-playing) AND (all:preference OR all:alignment OR all:personalization)' --time 10:00 --timezone Asia/Shanghai
"$research_python" -m research_ideation.admin --data-root /srv/research-data setup --profile default --project persona-preference
"$research_python" -m research_ideation.admin --data-root /srv/research-data doctor
"$research_python" -m research_ideation.admin --data-root /srv/research-data snapshot
```

无需创建 Alice、Bob、service 或逐一设置成员。setup 复用 default 的现有模型配置、链接插件并选定本人；如果希望使用已有命名 profile，替换 --profile 的值。

插件目录使用源码符号链接，更新后保留源码原位置。Hermes 依赖准备期间不要同时编辑其正在读取的发布输入；命令失败时保留返回的诊断，修复后重复 setup。

## 从已有版本升级

在服务器仓库执行 git pull --ff-only，然后用服务器原有实际 Python 和 data-root：

```bash
"$research_python" -m research_ideation.admin --data-root /srv/research-data inspect
"$research_python" -m research_ideation.admin --data-root /srv/research-data setup --profile research-me --project persona-preference
"$research_python" -m research_ideation.admin --data-root /srv/research-data current
"$research_python" -m research_ideation.admin --data-root /srv/research-data doctor
"$research_python" -m research_ideation.admin --data-root /srv/research-data snapshot
```

research-me 是示例，使用实际保存你资料的个人 profile。不要在已有部署重复 init / project-add，不为改成单用户另建空白身份。

setup 先做登记库一致性备份，再扩展单用户选择表；profile 配置变更也自动备份。保留原 user_id、私人目录、项目记录和调度编号。历史 Alice/Bob 不删除或合并，本插件拒绝它们作为未选研究身份调用。

若原项目只有一个登记的 service，默认继续使用它采集，避免原 cron 失效。可加 --service-profile 明确选择。--no-service 仅取消本插件的服务选择，不停止其原生任务；先核对并处理原 cron，再迁移调度，不能让两个任务同时运行。

这次不自动重启网关、抓取论文或调用模型。最后退出旧会话并重新打开，或使用 /new。

## PostgreSQL

按 [存储与审核](../ALIGNMENT.md) 绑定 CRA 仓库、Python 和服务器 .env。密钥留在服务器，不能进 Git。

```bash
"$research_python" -m research_ideation.admin --data-root /srv/research-data shared-bind --python /actual/cra/python --repository /actual/character-research-agent --env-file /actual/character-research-agent/.env
"$research_python" -m research_ideation.admin --data-root /srv/research-data shared-check
```

shared-bind 自动使用当前默认项目。shared-check 的连接、业务表和 ready 都要核对；配置了连接不等于数据库已经就绪。本次单用户升级不重建线上表、不修改 PostgreSQL GRANT/RLS。

当前仍保留本地私人记录、项目采集 SQLite 和 PostgreSQL 共享知识的组合，不要求现在迁移 Hermes 原生会话及记忆。

## 手动验收后启用每日采集

```bash
"$research_python" -m research_ideation.admin --data-root /srv/research-data update
"$research_python" -m research_ideation.admin --data-root /srv/research-data snapshot
"$research_python" -m research_ideation.admin --data-root /srv/research-data schedule
```

新部署由个人 profile 执行，旧部署优先使用已选采集 service。默认是 no-agent 脚本抓取，不调用模型。项目时区与实际采集 profile 的时区必须一致，默认为每天 10:00、Asia/Shanghai。

使用相同 Hermes root 和实际采集 profile 检查原生 cron list，并按该安装的正常方式运行 gateway/scheduler。schedule 仅建立任务，不启动 scheduler，也不证明定时触发成功。存在原任务但归属不一致时会拒绝重复创建，需先人工核对原生调度。

auto-explore 默认关闭。需要自动产生 idea 时，再明确调整原任务并配置模型；不会在升级中悄悄切成付费 Agent 任务。

## 进入聊天与使用

使用相同 Home / profile 启动已有 Hermes，开启新会话，加载 research-ideation:project-assistant；具体难点加载 research-ideation:problem-exploration。

Windows 使用 run.ps1 自动读取当前选择；Linux 可使用原 Hermes -p <已选名称> chat。default 需要使用 init 记录的真实 Hermes root；不要被其他终端的 sticky profile 或 HERMES_HOME 指向不同目录。

## 运行边界和迁移

一个个人身份有完整常用原生工具，不新增 Docker、执行沙箱或休眠管理。当前账号的系统文件权限就是实际操作范围。

社交软件接入继续关闭；后续只接本人白名单，再考虑多人。多用户 Docker/沙箱调研作为未来设计保留，不是本次部署步骤。

跨 Windows/Linux 时重新配置本机路径、原生 Home、插件链接和 Python；不能直接使用 Windows runtime.json、junction 和 cron 脚本。历史业务数据迁移要做一致性备份和身份重绑定，不盲目复制注册表中的绝对路径。源码和运行数据分开备份。
