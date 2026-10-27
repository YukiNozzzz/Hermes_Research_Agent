# Research Ideation

Hermes 的六类资料构思插件：PostgreSQL 提供共享资料，当前会话模型负责想 idea，默认直接在对话中输出。用户要求时再用 Hermes 文件工具整理成本地文档。

## 入口与运行流程

只有 **1 个工具 `research_start(question, constraints)` 和 1 个 Skill `problem-exploration`**。

```text
业务问题与约束 → PostgreSQL 六类完整资料 → Hermes 比较、质疑、修订
                                              ↓
                                        在对话中输出 idea
                                              ↓ 用户要求保存
                                        用户本地持久化目录
```

research_start 只读资料，不创建任务、不调用模型、不写数据库，也不自动生成报告。没有 research_finish。引用和输出质量由模型按 Skill 检查，不再提供旧版固定任务快照及提交校验。

在本机启动新的 Hermes 会话：

```powershell
$env:HERMES_HOME = (Get-Content E:/harness/research-data/control/runtime.json -Raw | ConvertFrom-Json).hermes_root
hermes -p default chat
```

输入示例：

> 加载 research-ideation:problem-exploration。根据六类资料，研究如何改善强人设用户的偏好冲突。比较不同机制，提出一个值得先验证的 idea，直接在对话中说明依据、未知项和最小实验。先离线验证，暂缓扩训。

需要文件时再说“把这个 idea 整理成 Markdown，保存到我的工作目录”。文件读写工具由 Hermes 提供，插件不新增导出或报告工具。

## 数据边界

| 数据 | 保存位置 |
| --- | --- |
| experience、decision、experiment、online、diagnosis、proposal | 现有 CRA PostgreSQL public.records |
| 资料出处、引用和历史版本 | CRA 现有 sources、record_sources、record_links、record_revisions |
| 聊天历史、个人记忆和配置 | Hermes 当前用户本地持久化目录 |
| 新 idea | 默认只出现在对话里；用户要求时保存本地文档 |
| 用户身份 | 本地部署配置保留稳定 user_id，不上传用户信息表 |

插件以一次 REPEATABLE READ、READ ONLY 事务批量读取完整正文、来源和引用，不进行检索、排序选优、摘要或条数截断。返回真实原生 ID、version、status、sources 和 links；proposal 保留为 proposal，不转成 idea。输出过大时模型必须说明无法完整审阅，不能悄悄筛选或声称读完。

所有审核状态均返回。draft 可用于形成明确标注未经确认的假设；confirmed 表示人工确认资料，不代表证明因果；rejected/superseded 用于历史对照与反证。缺项保持为空，不虚构收益或结论。

资料范围来自本地 project_id 配置，模型不能传用户、项目、SQL 或路径改变范围。有项目标记的资料仅匹配当前项目；`_ri.visibility=private` 不作为共享资料返回。无项目标记的旧资料默认不读，只有管理员显式配置 include_unscoped=true 才授权读取。

**当前部署授权的旧共享资料没有项目标记，因此启用了 include_unscoped；这不是多个项目之间的完整权限系统。** 0.8.0 切换时 public.records 有 329 条 decision 和 347 条 experiment，均为 draft，其余四类为空。数量和状态会随人工资料管理变化。插件不自动审核资料。

## 配置和检查

本地连接配置位于 data_root/control/database.json；凭据由指定环境文件中的 CRA_DATABASE_URL 提供，不打印到工具结果。复用现有 CRA Python 的 SQLAlchemy/psycopg 环境，本轮未重做数据库驱动或 Docker 部署。

从项目目录执行，Python 3.11+：

```powershell
uv run --no-project python -B -m research_ideation.admin current
uv run --no-project python -B -m research_ideation.admin database-check
```

新环境绑定示例，替换实际路径和稳定用户编号：

```powershell
uv run --no-project python -B -m research_ideation.admin database-bind --python E:/character-research-agent/.venv/Scripts/python.exe --repository E:/character-research-agent --env-file E:/实际凭据文件 --project persona-preference --user-id 实际用户编号 --title 人设偏好研究 --include-unscoped
```

只有确定这批无项目标记的旧资料应作为此部署的共享输入时，才加 --include-unscoped。绑定只检查现有业务表，写入本地连接配置，不建表。插件启动注册不连接数据库。

绑定到 Hermes Home 的 plugins/research-ideation，配置保留现有其他项：

```yaml
plugins:
  entries:
    research-ideation:
      settings:
        data_root: E:/research-data
platform_toolsets:
  cli:
    - hermes-cli
    - research_ideation
    - skills
```

本轮仍使用部署启动的 CLI；未实现消息平台的身份接入。更新后检查并开启新会话：

```powershell
hermes -p default plugins doctor research-ideation --ci
```

预期注册 1 个工具。数据库不可用时明确报错，不把失败解释为空资料或回退本地库。

## 人工资料管理

插件不再重复实现导入、审核或资料表。使用 CRA 已有的人工 CLI，环境文件及连接需先正确配置：

```powershell
# 在 CRA 项目及其 Python 环境中执行
python -m cra.cli schema proposal
python -m cra.cli import E:/实际资料.json --actor 实际录入人
python -m cra.cli inspect 实际记录编号
python -m cra.cli confirm 实际记录编号 --actor 实际确认人 --version 实际版本号
```

导入六类资料后仍为草稿，由人确认。不要把这些管理入口注册为模型可调用的上传/审核工具。新生成的 idea 不会自动成为 proposal。

## Docker 与后续扩展

每用户独立容器、独立 Hermes Home 和持久化卷，聊天历史与本地文件由 Hermes 管理。不要只把长期数据放在容器临时可写层，也不要把各用户 Home 挂成同一个目录。user_id 是部署元数据，尚未作为数据库登录认证。

读取事务防止插件误写，不等于数据库账号隔离。部署时应配置只读数据库权限。当前共用的资料集是组内共享输入；未来私人资料或多项目隔离还需要相应访问控制。后续可新增用户表并沿用稳定 user_id；本轮不提前建设用户平台。

## 代码与历史数据

| 文件 | 职责 |
| --- | --- |
| __init__.py、schemas.py、tools.py | 单工具和 Skill 注册、参数校验 |
| research_ideation/hermes.py、context.py | 本地 Hermes 运行范围和配置 |
| database.py、pg_worker.py | PostgreSQL 只读调用、范围筛选及批量读取 |
| ideation.py、records.py、models.py | 六类上下文、审核状态与公共校验 |
| admin.py | 本地连接配置和只读检查 |
| skills/problem-exploration/SKILL.md | 模型运行时构思及按需本地保存指令 |

0.8.0 移除任务、用户登记、idea 入库及报告保存逻辑，删除 tasks.py、registry.py、storage.py。旧 research_ideation schema 及 registry、records、record_versions、tasks、migration_archives 五张表已按用户要求删除，其中包含 20 条旧记录、22 个历史版本、7 个任务和 64 条迁移归档。public 下现有业务表保持不变；没有将旧记录自动转换或复制到六类资料中。仓库外本地历史封存副本未在此次删表操作中清理。

仓库只保留 README 和必要运行源码/Skill，不重新加入测试、示例、迁移文档或 run.ps1。迁移和验证脚本位于仓库外。本轮不修改现有可视化网页；新插件复用其已展示的 public 资料表。
