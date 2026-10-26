# Linux 单用户部署与升级

当前版本 0.4.0，目标是在一台服务器上先跑通一个人的研究流程。使用已有 Hermes 安装，不需要 Docker，不要求新建个人 Linux 账号，也不强制创建研究专用 profile。

## 先判断是否需要服务器

| 当前目标 | 操作 |
| --- | --- |
| 在 Windows 本机开发、手动验证研究流程 | 按 [快速使用](../QUICKSTART.md) 运行，不必先部署 Linux |
| 电脑关机后仍希望每天采集论文 | 把 Hermes、插件及调度放到持续运行的服务器 |
| 通过社交软件随时对话 | 需要持续运行的接入服务；本项目的真实聊天平台入口尚未实现 |

单用户减少的是账号和隔离配置，不免除服务器上的安装、数据路径配置、模型配置和调度管理。

deploy/ 当前只有这份说明和简明版 README.zh.md，不会被插件导入；其中没有需要启动的独立部署程序、Docker Compose 或自动安装脚本。源码上传到服务器后，也不会因 deploy/ 目录存在就自动开始运行。

## 准备

把源码放在固定路径，例如 /opt/research-ideation。数据放在独立且当前运行账号可写的位置，例如 /srv/research-data；这只是应用目录，不是 PostgreSQL 数据文件目录。

| 部分 | 示例位置 | 作用 |
| --- | --- | --- |
| Hermes 安装 | 安装器管理的真实位置 | 提供模型对话、原生工具和 scheduler |
| 本插件源码 | /opt/research-ideation | 包含工具、Skills 和业务代码，使用 Git 更新 |
| Hermes Home | /home/实际账号/.hermes 或已有 profile | 配置、凭据、会话、记忆及私人研究记录 |
| 应用数据 | /srv/research-data | 默认用户登记、项目原始论文和采集状态 |
| 共享 PostgreSQL | 已有数据库服务 | 明确共享的结构化研究知识 |

先确保源码、Hermes Home 和应用数据目录对实际运行账号可用。/opt、/srv 不是强制位置，没有写权限时可选择该账号自己的目录；不要让管理员创建的只读目录阻止运行账号保存数据。

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

如果已经完成 0.4.0 setup，且没有更换用户、默认项目或机器路径，后续拉取更新时保留原选择，先运行 current / doctor；需要重新合并插件配置或启用时可重复 setup，它不会重建用户和每日任务。

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

其中两个 Python 的用途不同：命令开头的 research_python 属于 Hermes，shared-bind 的 --python 属于 CRA、需要已安装其 PostgreSQL 依赖。数据库表结构由 CRA 的迁移维护；若表缺失，先修复 CRA 的数据库初始化，不对共享业务库执行测试降级或删表重建。

当前仍保留本地私人记录、项目采集 SQLite 和 PostgreSQL 共享知识的组合，不要求现在迁移 Hermes 原生会话及记忆。

## 手动验收后启用每日采集

```bash
"$research_python" -m research_ideation.admin --data-root /srv/research-data update
"$research_python" -m research_ideation.admin --data-root /srv/research-data snapshot
"$research_python" -m research_ideation.admin --data-root /srv/research-data schedule
```

新部署由个人 profile 执行，旧部署优先使用已选采集 service。默认是 no-agent 脚本抓取，不调用模型。项目时区与实际采集 profile 的时区必须一致，默认为每天 10:00、Asia/Shanghai。

使用相同 Hermes root 和实际采集 profile 检查原生 cron list，并按该安装的正常方式运行 gateway/scheduler。schedule 仅建立任务，不启动 scheduler，也不证明定时触发成功。存在原任务但归属不一致时会拒绝重复创建，需先人工核对原生调度。

### 确认任务属于谁

```bash
"$research_python" -m research_ideation.admin --data-root /srv/research-data current --collector
```

查看返回的 profile 和 home。新部署通常是 default；旧部署可能是 research-service。下面填写实际采集身份，不能把本人的聊天 profile 当成旧 service 的任务目录：

```bash
research_collector="default"
research_collector_root="$HOME/.hermes"
HERMES_HOME="$research_collector_root" "$research_python" -B -m hermes_cli.main -p "$research_collector" cron list
HERMES_HOME="$research_collector_root" "$research_python" -B -m hermes_cli.main -p "$research_collector" cron status
HERMES_HOME="$research_collector_root" "$research_python" -B -m hermes_cli.main -p "$research_collector" gateway status
```

default 的 root 就是 current 返回的 home；命名 profile 的 root 是其 home 的上两级目录。例如 home 为 /home/me/.hermes/profiles/research-service 时，root 为 /home/me/.hermes。三条原生命令必须来自前面已核对的同一个 Hermes 安装。

若该安装只有在指定源码后才能导入模块，原生命令也需要使用同一源码环境；init 的 --hermes-source 只供本项目调用 Hermes 时使用，不会永久修改你随后手工运行的 shell 环境。

### 启动和保持运行

先看 gateway status；已有网关服务就复用它，尤其不要给已由 multiplex Gateway 服务的 profile 再启动一个独立进程。若确认没有正在运行的网关，可前台验收：

```bash
HERMES_HOME="$research_collector_root" "$research_python" -B -m hermes_cli.main -p "$research_collector" gateway run
```

前台运行适合观察日志，不能把关闭 SSH 后仍会持续运行作为默认假设。长期运行应使用该 Hermes 安装的原生服务管理；先查看 gateway --help，再按支持的方式 install / start / status。服务器重启、退出登录后的服务存活也要单独验证，不在这里创建第二套 systemd 单元。

Hermes 官方提供 cron list、cron status 及原生 Gateway 服务方式，具体命令以服务器安装版本为准。[官方调度文档](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron)

auto-explore 默认关闭。需要自动产生 idea 时，再明确调整原任务并配置模型；不会在升级中悄悄切成付费 Agent 任务。

### 部署验收

| 检查 | 通过标准 |
| --- | --- |
| current | 用户、项目和 Home 都是这台服务器的实际选择 |
| doctor | configuration_ok 为 true，原生插件 doctor 通过；不能只看命令没有报错 |
| shared-check | 使用共享库时核对 ready=true；没有接库时不能声称已验证线上读写 |
| 手动 update / snapshot | 采集返回真实成功状态，论文和更新记录能检索到；失败不能当作零新增 |
| 聊天研究 | 新会话加载 Skill，能记录、检索、保存研究结果并关联反馈 |
| cron list / status | 正确 profile 下存在唯一任务，下一次时间和时区正确，调度器有实际心跳 |
| 定时触发 | 到点后能看到执行结果或失败记录；手动 update 不替代这个检查 |

原生 cron run 可以用于手动检查某个任务，但它会真实执行：先确认任务是 no-agent 采集脚本。若已改为 Agent 任务，可能调用模型，不要为了检查调度而无意启动付费研究。

## 常见问题

- SINGLE_USER_SETUP_REQUIRED：首次升级还没选择当前使用者，先执行 setup。
- SCHEDULE_PROFILE_CONFLICT：原任务不在当前采集 Home，检查 current --collector 和原生 cron，不删除登记编号来掩盖问题。
- SHARED_CONTEXT_UNAVAILABLE 或 ready=false：分别核对 CRA Python、配置路径、网络和业务表，不以本地结果冒充远程成功。
- install out of sync / Node / uv.lock 提示：修复匹配的 Hermes 安装；本插件 doctor 导入通过不表示整个聊天环境已正常。
- /new 后工具仍不对：核对插件链接、当前 Home、启用状态和长期运行网关是否加载了更新，不复制其他 profile 的密钥解决。

## 进入聊天与使用

使用相同 Home / profile 启动已有 Hermes，开启新会话，加载 research-ideation:project-assistant；具体难点加载 research-ideation:problem-exploration。

Windows 使用 run.ps1 自动读取当前选择；Linux 可使用原 Hermes -p <已选名称> chat。default 需要使用 init 记录的真实 Hermes root；不要被其他终端的 sticky profile 或 HERMES_HOME 指向不同目录。

## 运行边界和迁移

一个个人身份有完整常用原生工具，不新增 Docker、执行沙箱或休眠管理。当前账号的系统文件权限就是实际操作范围。

社交软件接入继续关闭；后续只接本人白名单，再考虑多人。多用户 Docker/沙箱调研作为未来设计保留，不是本次部署步骤。

跨 Windows/Linux 时重新配置本机路径、原生 Home、插件链接和 Python；不能直接使用 Windows runtime.json、junction 和 cron 脚本。历史业务数据迁移要做一致性备份和身份重绑定，不盲目复制注册表中的绝对路径。源码和运行数据分开备份。
