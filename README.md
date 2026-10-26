# 项目研究助手：research-ideation

Hermes 插件，版本 0.3.0。支持项目记忆、每日 arXiv 更新、针对研究难点的 idea 探索、反馈，以及个人与项目内容的明确共享。

- [快速使用](QUICKSTART.md)：Windows 启动、对话示例和管理命令。
- [存储与审核](ALIGNMENT.md)：CRA PostgreSQL 连接、记录状态、共享及迁移。
- [部署说明](deploy/README.md)：Linux 初始化、profile、调度和运行边界。
- [权限与升级](PERMISSIONS.md)：内部用户完整常用工具、受限 cron 服务，以及已有 profile 的权限升级。

## 启动

本机已配置运行环境时，在 PowerShell 中执行：

```powershell
cd E:\harness\research-ideation
.\run.ps1 -Profile research-alice
```

进入新会话后输入：

> 加载 research-ideation:project-assistant，看看 persona-preference 项目的已有资料和未解决问题。

探索具体问题时加载 research-ideation:problem-exploration。方案默认私有，明确共享后才会发布；人工审核和共享范围分别管理。

本机研究方向为“人设对话领域如何对齐用户偏好”，项目 ID 为 persona-preference，论文更新设为每天 10:00、Asia/Shanghai。调度需要 Hermes gateway / scheduler 持续运行。

## 数据归属

| 内容 | 保存位置 |
| --- | --- |
| 私有记录、研究任务、反馈和报告 | 各用户 Hermes profile 下 plugin-data/research-ideation |
| 项目原始论文、问题和采集状态 | data_root/projects/<project_id> |
| 已确认的共享知识、显式发布的方案草稿 | character-research-agent 的 PostgreSQL |
| 用户、成员和渠道绑定 | data_root/control/registry.sqlite |
| 本机运行路径与共享库绑定 | data_root/control/ 下的配置文件 |

源码仓库不保存业务数据库、密钥、虚拟环境或运行结果。CRA 公共数据库当前仅绑定一个明确共享的项目，私有内容继续保留在各自 profile。

## 源码结构

```text
research-ideation/
├── plugin.yaml、__init__.py   # Hermes 插件声明与注册
├── schemas.py、tools.py      # 9 个工具的参数和处理入口
├── research_ideation/
│   ├── records.py            # 结构化字段和审核规则
│   ├── store/                # 本地 / PostgreSQL、迁移、登记与事务
│   ├── runtime/hermes/       # Hermes profile、会话与 cron 适配
│   ├── adapters/             # arXiv、本地材料、未来渠道接入
│   ├── workflows/            # 每日论文采集流程
│   ├── memory.py、knowledge.py # 项目概览、记录、检索与阅读
│   ├── tasks.py、sharing.py  # 研究任务、反馈、发布与撤回
│   └── admin.py              # 本机管理员入口
├── skills/                   # 项目助手和问题探索指令
├── run.ps1                   # Windows 聊天 / 管理入口
├── config.example.yaml       # 非敏感 profile 配置示例
├── config.service.example.yaml # 受限后台服务配置示例
├── PERMISSIONS.md            # 两种身份及旧配置升级
├── pyproject.toml            # 包信息和命令入口
└── deploy/README.md          # 部署步骤
```

storage.py、registry.py、profiles.py 和 adapters/hermes.py 是兼容导入入口，仍被运行代码使用。Python 包中的 __init__.py 也保留。

## 当前边界

独立 Deep Research、向量检索、PDF / 对象存储和真实微信消息入口尚未实现。内部用户开放 Hermes 原生常用工具，同项目成员具有相同业务权限；后台服务保持受限。Profile 与应用权限检查不构成操作系统沙箱，当前部署假设内部成员相互信任。

Linux 首次部署需要重新登记解释器、源码、profile 和共享库路径，不能直接复制 Windows 虚拟环境或运行配置。数据库持久化、备份及真实渠道接入需单独配置。

## 更新记录

### 2026-10-26

- 更新至 0.3.0：只保留 user / service，普通用户恢复原生工具与个人记忆；同项目成员同权限。新增 permissions-sync 预览、配置备份与幂等升级，旧 owner / editor / reader 兼容映射为 user；doctor 按身份校验，后台服务不能执行人工审核。
- 同步 Linux 首次部署、已有服务器升级和通俗说明，提供用户 / 服务两份配置示例；本机 12 项权限回归、原生工具解析和四个 profile 的插件 doctor 已通过。真实数据库业务表就绪状态仍需另行核对。
- 更新至 0.2.0：接入 CRA PostgreSQL 共享知识，支持显式发布方案草稿、人工审核、版本引用和撤回，个人内容继续按 profile 隔离。
- 将数据库实现集中到 store/，Hermes 专有实现集中到 runtime/hermes/，保留旧导入路径的兼容入口。
- 清理测试代码、验收脚本、历史规划文档和未使用的预留模块；精简说明，Windows 入口保留聊天与管理两种模式。

**拉代码后：** 按 [权限升级](PERMISSIONS.md) 预览并执行 permissions-sync，再开启新会话。先备份已有 SQLite；旧库首次读取会升级到 v2。使用共享数据库时，按 [对齐说明](ALIGNMENT.md) 配置本机 shared-bind 路径。密钥、数据库及运行结果不随源码提交。
