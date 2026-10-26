# 项目研究助手：research-ideation

Hermes 插件，版本 0.4.0。当前面向一个研究者：整理项目背景和历史、每日拉取 arXiv 论文、针对难点提出可验证的 idea，并保存实验反馈。

- [快速使用](QUICKSTART.md)：选择自己的 profile、启动聊天和常用命令。
- [Linux 部署](deploy/README.md)：首次安装、已有版本升级和实际调度。
- [单用户设置与权限](PERMISSIONS.md)：历史用户保留、默认 profile 和工具能力。
- [存储与审核](ALIGNMENT.md)：本地资料与 CRA PostgreSQL 的读写、发布及人工审核。
- [未来多用户隔离方案](MULTI_USER_ISOLATION_PLAN.md)：Docker / 自定义沙箱调研；当前阶段暂缓实施。

## 单用户入口

首次从已有版本升级，在 PowerShell 中选择你实际使用的个人 profile：

```powershell
cd E:\harness\research-ideation
.\run.ps1 -Mode admin -Arguments @('setup','--profile','research-me','--project','persona-preference')
.\run.ps1
```

research-me 是本机已有个人 profile 的示例；服务器使用自己的实际名称。也支持 --profile default，直接使用 Hermes 原有默认 Home。新安装没有必要创建 Alice、Bob 或独立的 service 用户。

setup 记录当前使用者和默认项目，自动建立成员关系并配置研究插件，保留模型设置。已有用户会保留原 user_id，避免私人记录失去归属。其他历史用户和目录不删除、不合并，但不能再通过本插件作为并行研究用户使用。

选择后，日常命令可以省略 profile 和 project：

```powershell
.\run.ps1 -Mode admin -Arguments @('current')
.\run.ps1 -Mode admin -Arguments @('doctor')
.\run.ps1 -Mode admin -Arguments @('snapshot')
.\run.ps1 -Mode admin -Arguments @('update')
.\run.ps1 -Mode admin -Arguments @('schedule')
```

update 会真实访问 arXiv；schedule 创建每日任务，但不会自动启动 gateway。新安装由个人 profile 执行采集；旧项目唯一的 service 采集身份会自动保留，以免原 cron 失效或重复创建。

## 研究闭环

启动新会话后输入：

> 加载 research-ideation:project-assistant，看看我的项目目标、已做工作和未解决问题。

> 针对角色设定与用户偏好冲突的问题，加载 research-ideation:problem-exploration，结合已有资料提出验证方案并保存。

> 我试过刚才的方案，结果是……。请把反馈关联到对应 idea。

默认研究方向为“人设对话领域如何对齐用户偏好”，现有项目 ID 为 persona-preference，采集时间为每天 10:00、Asia/Shanghai。工具省略 project_id 时使用 setup 选定的项目，不再要求每次指定身份。

私人记录和项目研究资料仍明确区分：日常记录默认私人，明确发布后才进入项目范围。即使现在只有一个人，也不会自动把私人笔记传到共同资料库；人工审核规则继续保留。

## 数据保存

| 内容 | 位置 |
| --- | --- |
| 个人记录、研究任务、反馈和报告 | 当前 Hermes Home 的 plugin-data/research-ideation |
| 原始论文、项目问题、采集状态 | data_root/projects/<project_id> |
| 已确认共享知识、显式发布的结构化方案 | CRA PostgreSQL |
| 当前用户、默认项目、历史身份和可选旧采集身份 | data_root/control/registry.sqlite |
| 本机解释器与共享库路径 | data_root/control/ 下的配置文件 |

业务数据、模型密钥、数据库连接和虚拟环境不进 Git。当前存储仍是本地 SQLite / 文件加线上 PostgreSQL，不要求把 Hermes 会话与记忆全部迁入数据库。

## 代码位置

- research_ideation/runtime/hermes/single_user.py：单用户 setup、默认 Home 接入、登记库一致性备份和旧采集身份复用。
- research_ideation/store/registry.py：当前使用者、默认项目与历史身份；运行请求只接受选定身份。
- run.ps1：自动读取当前选择，使用登记的真实 Home 启动。
- research_ideation/admin.py：管理命令，默认选择当前用户与项目。
- research_ideation/workflows/daily_update.py：本人或已选旧 service 的采集与每日去重。
- research_ideation/store/、tasks.py、sharing.py：存储、研究任务、反馈、发布与审核。
- skills/：项目助手与问题探索流程。

## 当前边界

当前按单用户可信本机运行，文件、终端等 Hermes 原生工具保持可用。没有 Docker、自定义执行沙箱、自动休眠或多用户社交入口；profile 不是系统文件权限边界。

社交平台接入仍未实现，非 CLI 入口继续返回 CHANNEL_NOT_CERTIFIED。后续先接本人白名单，再另行考虑多用户。

## 更新记录

### 2026-10-26

- 0.4.0：增加单用户 setup/current；允许复用默认 Home；聊天及常用管理命令自动选用户和项目。本人可以抓取和调度论文，不必创建 service；兼容保留旧采集身份和 cron。
- 升级保存原用户编号和私人数据，其他历史 profile 不删除或合并；当前插件只接受选定身份。同步工具说明、Skills 和 Windows / Linux 文档。
- 0.3.0：统一 user/service 权限及原生工具配置；0.2.0 接入 CRA PostgreSQL。

**拉代码后：** 已有部署先按 [部署说明](deploy/README.md) 运行一次 setup，选择已有个人 profile，再开启新会话；不能仅执行 permissions-sync。线上数据库业务表及实际定时运行需分别验收。
