# 部署说明（人话版）

0.3.0 已切换为两种身份：内部 user 可使用完整常用工具，后台 service 受限。全新服务器按下文初始化；已经部署过的服务器只需拉取代码并执行权限升级，不重建 profile 或定时任务。升级命令和验收顺序见 [主部署文档](README.md#已有服务器升级至-030)。

> 逐节对应 [README.md](README.md)。原文是给装服务器的人看的电工手册，这份是给住户看的说明：左边摘一句原文，右边说它到底什么意思、你要做什么。

## 先把六个词对上号

```
Hermes        这栋楼里唯一的"总管家"，会聊天、会干活
profile       管家的"分身"，每人一个：自己的记性、配置、钥匙串
plugin 插件   给管家加的一门手艺，比如"研究助手"。代码只有一份，所有分身共用
gateway       管家的大脑进程，必须一直醒着，闹钟才会响
cron job      闹钟："每天 10 点去抓论文"
data root     公共档案室，默认 /srv/research-data
私有记录      每个分身自己抽屉里的东西（profile 下的 plugin-data）
```

---

## 1. 部署与边界

> 原文：使用已有 Hermes，不另建实验 HERMES_HOME。用户 profile 是多用户运行载体，不能当作操作系统沙箱。

人话：别为了这个插件再装一套 Hermes，就用服务器上跑着的那套。profile 只是"分身的配置和记性"，不是"独立的房间"——同一个系统账号下，分身之间能互相看见文件。

→ 落地：直接用现有的 `~/.hermes`，不为插件新建 HERMES_HOME。

---

## 2. 上传什么

> 原文：用 Git 推送本仓库源码即可，保留 plugin.yaml、根注册入口、schemas.py、tools.py、research_ideation/、skills/ 和 pyproject.toml。缓存、虚拟环境、密钥、本机运行配置和数据库不放进 Git。

人话：搬家公司只搬家具，不搬钥匙和账本。Git 里只放"图纸"（能重建一切的那部分源码）。

不进 Git 的四类东西，每类都有理由：

```
缓存 / 虚拟环境     换台机器尺寸就不合，重建比搬便宜
密钥               泄露就是事故
runtime.json       记的是这台机器的绝对路径，换机器全是错的
registry.sqlite    记的是本机 profile 位置和 job 编号，同上
```

→ 落地：`git clone` 之后不需要"恢复"任何运行态；运行态在新机器上重新生成。

---

## 3. Linux 首次测试

> 原文：先按服务器已安装 Hermes 的实际配置找到可用 Python，在仓库根目录执行 `"$research_python" -c 'import hermes_cli.main'`。第一条导入检查失败时，先确认 Hermes 的 Python / 源码环境，不用系统 Python 代替。

人话：先找个"会说 Hermes 这门语言"的 Python，再动工。这行 import 就是在试它会不会说。

为什么不能用系统 Python：Hermes 的依赖（ruamel、各种 provider SDK）只装在它自己的环境里，系统那个一 import 就报 `ModuleNotFoundError`。

→ 落地：找到那台机器上 Hermes 实际使用的解释器，把它记成 `$research_python`，后面所有命令都用它。init 时还要 `--hermes-python "$research_python"`，否则定时任务会用错解释器、静默失败。

---

## 4. 初始化

> 原文：首次测试顺序：初始化 → 创建项目和 profile → 设置成员 → 配置用户模型 → doctor → 手动更新论文 → 查询概览 → 新会话中探索。手动流程通过之后，再执行 schedule。

人话：建房 → 挂牌 → 建分身 → 发门禁卡。顺序不能乱。

八条命令其实只有四个动作：

```
init                    建档案室（/srv/research-data/control + projects）
project-add             挂项目牌子：ID、方向、arXiv 查询式、每天几点
user-add ×3             建三个分身：alice、bob、paper-service（值班机器人）
member ×3               登记项目成员：alice、bob 都是 user，paper-service 是 service
```

为什么顺序不能乱：`user-add` 会顺手 `hermes profile create` 并启用插件，它还要求档案室已经存在；`member` 又要求人和项目都已经登记。

> 原文：user-add 会创建并启用插件，不要把服务器已有的同名个人 profile 当作空白测试 profile。

人话：如果服务器上已经有人叫 `research-alice`，别拿它当测试用的空白身份——换一个没被占用的名字。

→ 落地：名字冲突就换名，后续示例同步改。

---

## 5. 实际调度

> 原文：job 创建后还需要 Hermes gateway / scheduler 实际运行。使用当前安装支持的启动方式，不能重复启动冲突的网关。可用原生 cron run 手动验收脚本；手动执行不等于已经观察到每天 10:00 的定时触发。

人话：`schedule` 只是把闹钟写进本子；真正按响它的是 gateway 那个进程，所以它必须一直开着。手动按一下响了，不代表明早 10 点它会自己响——那是两件事。

怎么区分这两件事：

```
配置对不对     hermes -p <profile> cron list      看得到 job、schedule、下次时间
跑得通不通     hermes -p <profile> cron run <id>  立刻跑一次，看 runs 里的 completed
会不会自动跑   cron status 里 gateway 活着 + ticker heartbeat 在跳
```

→ 落地：一个网关只能有一个。已经有网关在跑就复用它，别再起第二个。

---

## 6. 研究与模型

> 原文：内部 user 使用 hermes-cli + research_ideation + skills，保留个人记忆；service 仅保留研究工具与 skills，关闭个人记忆。collect-only 的服务 cron 不需要模型凭据。

人话：抓论文是一段死程序，不经过 AI，所以免费；"想问题"要调模型，才花钱。所以值班分身（只抓论文）不用配大脑，alice 和 bob 要配。

→ 落地：每个要聊天的 profile 自己配模型；不要在 profile 之间复制 `.env`。

---

## 7. 多用户隔离

> 原文：0.3.0 面向可信内部团队，只分 user / service；内部用户开放完整常用工具，profile 自身不提供磁盘隔离。

人话：现在大家是相互信任的内部成员。alice 和 bob 权限相同，都可以研究、改代码和运行测试；值班机器人专心处理后台任务。各人的聊天和个人配置仍然分开保存，但同一个系统账号下，文件可能互相能读，所以不能把 profile 当作锁住的独立房间。

部署时按两种身份配置：

```
user       hermes-cli + research_ideation + skills；恢复个人记忆
service    research_ideation + skills；关闭个人记忆与后台审查
```

这只调整模型能调用的工具，不卸载插件、不自动安装第三方 Skill，也不让数据库或系统账号变成超级用户。原生工具仍需要相应环境和凭据。已有 profile 使用 permissions-sync --all 预览，再加 --apply 应用；配置会备份，之后开启新会话。详见 [权限说明](../PERMISSIONS.md)。

> 原文：当前插件对非 CLI 的原生消息入口返回 CHANNEL_NOT_CERTIFIED。

人话：微信、Telegram 这些入口现在会被硬拒绝，只有命令行能用。想开放聊天软件，得先补接入元数据、命令门禁、并发和错发验收。

> 原文：管理员 / 同一 OS 账号直接操作文件不在应用级隔离承诺内。

人话：完整工具能访问运行账号本来就有权访问的文件。当前内部使用接受这个信任前提；若以后需要严格区分谁能看哪些文件，需要再做系统和数据库授权。

---

## 8. Windows 路径注意

> 原文：不要将本机 control/runtime.json 或整份 registry.sqlite 直接当作 Linux 配置……新服务器重新初始化、登记用户和创建调度；首次空白测试不迁移本机研究数据。

人话：给从 Windows 搬过来的人看的，一句话——旧地址簿作废。`E:\...` 的路径、旧机器的 job 编号，在新服务器上全是错的。

需要迁移历史数据时，那是另一件事：备份数据库 → 迁私有目录 → 重绑身份路径 → 回归来源和权限。不能顺手做，也别在首次测试时做。

---

## 9. 必要检查

> 原文：实际使用时还需检查保存的任务、证据、候选和报告，不能只看模型最终回答。

人话：模型说"我做完了"不算数，要去看它到底存了什么。

```
doctor --profile X                 按 user / service 检查工具与记忆策略、插件能否加载
snapshot --profile X --project Y   这个分身视角下，项目里到底有哪些记录
cron runs <job_id>                 闹钟真跑过没有、状态是什么
```

→ 落地：验收看数据，不看回复。

---

## 只记三件事

1. 一份代码、三个分身、一个公共档案室。分身之间**不是**隔离的，隔离靠"少给手艺"。
2. 门禁是插件自己查的，不是操作系统拦的——所以危险工具必须关。
3. 旧机器的运行配置和数据库一律不搬，新机器重新初始化。

---

## 附：本机实测补充（2026-10-26）

部署机上踩到两个原文没写的情况，留着备查：

1. **宿主机没有时区数据库。** `/usr/share/zoneinfo` 缺失时，`ZoneInfo("Asia/Shanghai")` 直接抛错，`project-add` 会死在设置时区那一步。修法：装系统 `tzdata`（Ubuntu 上 `apt install -y tzdata`，注意这个镜像没有 `apt-get`）。
2. **Hermes 的 cron 不支持时区。** `hermes cron create` 没有 `--timezone` 参数，job 里存的是 `"timezone": null`，按宿主机本地时间算。宿主机是 UTC 时，插件写的 `0 10 * * *` 会在北京时间 18:00 触发。修法二选一：把 job 改成 `0 2 * * *`（UTC 02:00 = 北京 10:00，中国无夏令时），或者把宿主机时区设成 Asia/Shanghai 并保持 `0 10 * * *`。两者不能混。
