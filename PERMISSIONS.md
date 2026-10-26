# 单用户身份与工具权限

0.4.0 当前只服务一个研究者，不要求搭建 Docker、执行沙箱或多用户账号体系。研究者继续使用 Hermes 原生文件、终端、记忆和研究工具，权限受当前操作系统账号约束。

## 当前身份

setup 在登记库中选定一个 owner_id、默认 project_id，以及可选的旧 service_id。业务 user_id 与历史数据归属保留；owner_id 在此只是“当前研究者”的字段，不是新增一套 owner/editor/reader 权限等级。

- 日常聊天、私人记录、研究任务和审核使用当前个人身份。
- 本人可以直接触发论文抓取，也可以在同一个 profile 中创建每日采集任务。
- 旧部署已经使用 service 时可以继续保留。它仍无私人数据区、不能人工审核，普通聊天不会默认切到 service。
- 多个历史人类用户仍保存在登记库，但研究请求只接受当前选定者。管理员可重新 setup 选择另一个原有身份查看其原有资料，不能据此声称文件已经系统隔离。

## 一次性选择

```powershell
.\run.ps1 -Mode admin -Arguments @('setup','--profile','research-me','--project','persona-preference')
.\run.ps1 -Mode admin -Arguments @('current')
```

也可以选择 default；新安装无需额外命名 profile。已有私人数据不会自动合并进默认 Home，setup 拒绝为已有 profile 改 user_id，防止原数据被误认为别人的记录。

新安装不需要 user-add / member。旧命令保留兼容，但在选定用户后不能继续注册额外研究用户。

## 已有 service 与 cron

setup 默认保留该项目唯一的已登记采集 service。也可用 --service-profile 明确选择。若不再选择旧服务，用 --no-service；这不会停止原 Hermes 网关或删除其 cron，必须先在原生 Hermes 中核对、停止或迁移旧任务。

已有 job_id 继续保留。schedule 在当前采集 profile 找不到原任务时会报 SCHEDULE_PROFILE_CONFLICT，不自动创建重复任务。不要为了消除报错手工删除登记库任务编号；先核对实际 cron。

## 原生能力

个人身份使用 hermes-cli、research_ideation、skills，并开启原生个人记忆。配置合并会保留模型、凭据引用和其他设置，不自动打开付费后台审查。

可选 service 只使用 research_ideation、skills，关闭个人记忆。文件、终端等工具是否可运行，还取决于 Hermes 安装、依赖和服务凭据。

```powershell
.\run.ps1 -Mode admin -Arguments @('permissions-sync')
.\run.ps1 -Mode admin -Arguments @('permissions-sync','--all','--apply')
```

第一行默认预览本人；--all 表示本人和已选旧 service，不再遍历全部历史用户。--apply 在 profile 内备份配置，之后开启新会话。

## 数据和边界

私人 / 项目范围和人工审核继续保留，避免把个人资料自动发布到 PostgreSQL。单用户不代表所有资料都要设成项目共享。

当前没有系统沙箱。同一系统账号拥有的文件，Agent 的原生工具可能访问到；这个版本以本人操作自己的服务器为边界。接入第二位用户时应先实施独立运行环境，不直接开放全部历史 profile。

真实社交软件入口未实现，当前非 CLI 请求仍拒绝。后续本人聊天入口也需要平台认证和账号白名单。
