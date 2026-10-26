# 单用户部署：简明版

现在先让一个人的研究流程跑通：一个 Hermes，使用你自己的默认 Home 或已有个人 profile。Docker、多用户路由和自定义沙箱暂缓。

完整命令见 [部署说明](README.md)。

## 现在是否要部署

- 只在 Windows 本机开发、手动测试：先看 [快速使用](../QUICKSTART.md)，不用先操作 deploy/。
- 希望电脑关机后每天仍能采集：把程序和调度放到常开的服务器上。
- 希望接社交软件：还要开发真实接入，单纯部署现在的插件不会自动得到微信机器人。

deploy/ 目前只有说明文档，不是后台程序，也没有 Docker 或自动部署脚本；保留它供迁移和运维查阅即可。

## 已经部署过

1. 拉取最新代码，保留原有数据目录和服务器配置。
2. 用 inspect 查看原登记，选择保存你真实资料的个人 profile。
3. 执行 setup --profile 你的实际名称 --project persona-preference。
4. 执行 current、doctor、snapshot；使用 PostgreSQL 时再检查 shared-check。
5. 重新开启 Hermes 会话，开始研究。

setup 不会清除 Alice/Bob、不合并私人记录，也不会把它们的模型凭据复制给你。它会保留选定人的原 user_id，并保存登记库和配置备份。

旧项目已有唯一的 service 采集身份时会继续复用，cron 不重建。不要为了改成单用户删掉旧任务或登记编号。

## 第一次部署

先装好并配置 Hermes，然后：

初始化应用 → 建研究课题 → setup 选择 default → 检查 → 手动抓取论文 → 对话探索 → 最后启用每日任务。

不需要创建多人账号，也不需要额外 service。本人 profile 就可以执行无模型的每日论文采集。

## 数据放哪里

- 私人记录和研究报告：你的 Hermes Home。
- 原始论文与采集状态：独立的 research-data。
- 明确共享的结构化知识：线上 PostgreSQL。
- 源码、密钥、运行数据分别管理。

文件和会话不会因为选择单用户就全部改存 PostgreSQL。个人笔记默认也不会自动发布到公共库。

## 每日任务

默认每天 10:00，Asia/Shanghai。schedule 只是创建任务，Hermes gateway/scheduler 仍要持续运行。手动 update 成功和真正等到定时触发是两项不同验收。

先用 current --collector 查实际执行采集的 profile，再到同一个 Hermes Home 检查 cron list、cron status 和 gateway status。新部署通常是本人，旧部署可能仍是 research-service，不能查错目录后误以为任务不存在而再建一份。

完整说明中已补上前台运行、长期服务、数据库就绪和到点验收的操作。若已有网关就复用，不另启动第二个网关。

当前没有微信真实入口；后续先接你本人账号，不直接开放其他人使用。
