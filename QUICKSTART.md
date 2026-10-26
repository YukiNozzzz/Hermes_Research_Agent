# 单用户使用说明

0.4.0 优先完成一个人的研究闭环。你可以直接使用 Hermes 默认 Home，也可以选择已有个人 profile。后台论文采集默认由同一个 profile 执行；升级旧部署时可以继续复用已有 service。

本文是 Windows 本机入口，不要求先操作 deploy/ 或搭建 Docker。需要离开本机持续运行时，再按 Linux 部署说明迁移；本机任务的调度也需要实际 scheduler 持续运行。

## 本机从已有版本升级

在 E:\harness\research-ideation 运行：

```powershell
.\run.ps1 -Mode admin -Arguments @('inspect')
.\run.ps1 -Mode admin -Arguments @('setup','--profile','research-me','--project','persona-preference')
.\run.ps1 -Mode admin -Arguments @('current')
.\run.ps1
```

research-me 是个人 profile 示例。选择你已有资料所属的真实 profile，不要为了改名新建一个用户。setup 会保留它原来的 user_id 和 Home；Alice / Bob 等历史验收身份仍留在登记库和磁盘上，但不再作为并行用户调用研究插件。

setup 在升级选择前用 SQLite backup 备份登记库；修改 profile 配置前另存 config.yaml 备份。重复运行不会重复创建用户，也不自动建立新 cron。若旧项目只有一个已登记 service，默认保留它，普通聊天仍使用本人。

setup 将采集所用 profile 的时区与项目一致，默认 Asia/Shanghai；个人 profile 也按默认项目时区配置，原配置会备份。

如果你准备改用 Hermes 默认 Home：

```powershell
.\run.ps1 -Mode admin -Arguments @('setup','--profile','default','--project','persona-preference')
```

这会选择默认 Home 自己的记录，不会把 research-me 或 Alice 的私人资料自动搬进去。已有私人记录应继续使用其原 profile。

## 聊天

```powershell
.\run.ps1
```

脚本读取当前选择，不再固定打开 research-alice。模型配置保存在选定 Home；没有替你配置模型或复制其他 profile 的 .env。

建议从这些对话开始：

> 加载 research-ideation:project-assistant，告诉我项目目标、之前做过什么，还有哪些未解决问题。

> 记录我的个人经验：……。

> 针对这个难点，加载 research-ideation:problem-exploration。先查已有材料，再提出可验证的 idea，并保存依据、风险和实验方案。

> 我验证后的结果是……，请记录为这个 idea 的反馈。

> 抓取一次最新相关论文，再告诉我新增了哪些内容。

工具可以省略 project_id，默认项目来自 setup。不会编造尚未提供的历史实验或人脑经验。idea 流程仍要求读取实际证据，资料不足时允许保存“暂无候选”。

## 常用管理命令

```powershell
.\run.ps1 -Mode admin -Arguments @('doctor')
.\run.ps1 -Mode admin -Arguments @('snapshot')
.\run.ps1 -Mode admin -Arguments @('update')
.\run.ps1 -Mode admin -Arguments @('schedule')
.\run.ps1 -Mode admin -Arguments @('current','--collector')
.\run.ps1 -Mode admin -Arguments @('shared-check')
```

update 真实访问 arXiv，同一项目、日期和检索词去重；失败不会伪装成没有新论文。schedule 默认创建不调用模型的采集脚本，时间来自项目设置。

schedule 不会自动启动 gateway，也不会证明每天 10:00 已经运行。使用实际 Hermes 安装的 cron list / gateway 管理方式检查。若旧任务不属于当前选择，命令会提示冲突，不偷偷再建一份。

current --collector 显示实际采集身份及 Home；不要只在聊天 profile 下查旧 service 的任务。Linux 的具体 cron/status、网关启动及验收步骤见 [部署说明](deploy/README.md)。

## 导入和审核

```powershell
.\run.ps1 -Mode admin -Arguments @('import-json','--file','E:/my-notes.json')
.\run.ps1 -Mode admin -Arguments @('review','--record','实际记录编号','--version','1','--status','confirmed')
```

私有是默认范围，--shared 才导入项目资料。结构化记录和 sources 的格式见 [存储说明](ALIGNMENT.md)。人工确认仍不注册为模型工具。

## 模型环境与路径

control/runtime.json 保存实际 Hermes root、Python 和源码位置。run.ps1 使用这些路径；当前 profile 可以处于另一个合法 Hermes root，脚本按其实际 Home 启动，兼容 Windows MSIX 路径差异。

新会话才会重新加载工具和技能。当前旧聊天不会因源码更新自动改成单用户会话。

如果 Hermes 自身提示 install out of sync、Node 或 uv.lock 依赖不同步，需要修复对应 Hermes 安装；插件 doctor 的导入通过不等于该安装的完整聊天环境已经正常。不要关闭依赖校验来绕过。

Linux 新部署见 [部署说明](deploy/README.md)，不要把 Windows 虚拟环境、junction 或 runtime.json 直接复制过去。
