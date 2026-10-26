# 与 character-research-agent 的上下文库对齐

版本：0.4.0，2026-10-26。当前是单用户应用，命令默认使用 setup 选定的本人和项目；可复用旧采集 service。权限与迁移见 [PERMISSIONS.md](PERMISSIONS.md)，本次不修改 PostgreSQL 角色授权。

当前实现是混合存储：CRA PostgreSQL 提供共享、已确认的研究知识；本地 SQLite 保留用户私有记录、研究任务和采集状态。显式发布的结构化研究记录写入同一 PostgreSQL，初始状态为 draft。没有复制另一套同名但字段不兼容的远程 records 表。

## 数据和模块归属

| 内容 | 保存在哪里 |
| --- | --- |
| 当前用户、默认项目、可选旧采集身份，以及历史 profile / 成员 / 渠道绑定 | control/registry.sqlite |
| 私人研究记录、未分享的 idea、任务快照、反馈 | 对应 profile 的 plugin-data/research-ideation |
| 项目原始论文、问题、更新批次、任务 | 原 data_root/projects/<project_id> SQLite |
| 共享研究知识、已发布方案草稿 | CRA PostgreSQL 的既有六张表 |
| Markdown / JSON 报告 | 原来按 profile / 项目和任务划分的 reports 目录 |
| 公共库绑定 | data_root/control/shared-context.json，只有路径与项目配置，不保存密码 |

数据库实现集中在 research_ideation/store/：

- local.py：本地记录、审核、任务事务、采集批次、来源与发布映射。
- registry.py：管理员登记库。
- migrations.py：SQLite v1 → v2 升级，不删除旧记录或历史。
- shared.py：可信项目绑定、子进程协议、返回记录规范化。
- pg_worker.py：使用 CRA 已有 Python 环境，复用其数据模型和字段校验，在同一套 PostgreSQL 表读写。
- interface.py：统一入口、可见范围、跨后端引用和共享发布。

根 storage.py / registry.py / profiles.py 和 adapters/hermes.py 保留兼容入口。Hermes 专有代码已移入 runtime/hermes/，业务流程不直接执行 SQL。

## 连接与授权

CRA 公共表目前没有项目和私有权限列，因此管理员只能把这套明确共享的公共库绑定到一个本地项目。所有原有无项目标签的 CRA 记录视为该项目共同资料；由本插件写入的记录另带不可由模型修改的 _ri.project_id 元数据。其他项目不能复用该绑定。每次调用前后重新验证原生 profile 与成员关系；这不等于远程 PostgreSQL 已有多租户隔离。

本机曾为 persona-preference 配置共享库绑定，但实际可用状态应以当前 shared-check 为准。Linux 部署需要重新配置三个路径：CRA 仓库、该仓库的可用 Python、该机器上的 .env；无需复制 Windows Python 环境。先完成单用户 setup，再执行示例：

```bash
python -m research_ideation.admin --data-root /srv/research-data shared-bind \
  --project persona-preference \
  --python /srv/character-research-agent/.venv/bin/python \
  --repository /srv/character-research-agent \
  --env-file /srv/character-research-agent/.env
python -m research_ideation.admin --data-root /srv/research-data shared-check \
  --project persona-preference
```

以上 python 使用部署文档中已核对的 Hermes 解释器；shared-bind 的 --python 则是装有 CRA 依赖的解释器。桥接复用 CRA 环境，不改变 Hermes 托管环境依赖。数据库地址或凭据只在 .env 中配置，不经模型参数传递。

## 记录、审核与引用

支持六类结构化研究内容：experience、decision、experiment、online、diagnosis、proposal；本地 idea 对应 proposal。note、problem、feedback、paper、update 保留其流程职责。

- fields 保存各类型字段；方案保存 bottleneck / change、假设、相关工作、实验和风险。
- status 独立于 visibility，使用 draft / confirmed / rejected / superseded。
- 模型保存的方案始终是 draft。确认不表示实验已成功或方案已被采纳。
- 决策结论、实验采纳理由、proposal 的 adopted / adoption_reason 等人工字段，不能由模型通过 research_record 填写；由本机管理入口补充。
- 修改已确认正文或字段，会回到 draft 并增加版本。
- 研究检索返回已确认知识、原始论文及明确标记的上下文笔记 / 问题；research_finish 只接受已确认知识或明确标注为原始材料的 paper 作为证据。上下文草稿不能绕过该检查。
- 原始论文允许阅读和引用实际摘要，但不因此变成人工确认的经验结论。新采集论文保存 URI、哈希、coverage 和定位；旧论文可从已有元数据恢复来源展示。

本地新增 sources、record_sources、record_links、record_revisions 和 shared_exports；history 保留用于兼容旧版报告引用。当前引用关系使用 cites。远程已有的其他关系保留在 native_links 中，不能将尚未实现的本地关系当作已支持。

共享库记录使用 `cra:<原编号>`，例如 cra:exp-20261026-ri-shared-acceptance。引用仍固定 id/version/quote，历史草稿不能冒充已确认版本，原文摘录须匹配。远程撤回 / 状态失效后不能用旧版本继续读取。确认或撤回远程记录时，检查仍在使用的依赖。

## 使用

新 Hermes 会话加载原来的两个 Skill 即可，仍使用原来的 9 个工具。research_search / research_read 会自动合并被授权的共享上下文。明确要求分享一个私有方案时，research_publish 会创建项目发布副本，并将结构化内容导出为 PostgreSQL draft；没有自动导出整段会话、私有资料或未分享任务。

跨 SQLite / PostgreSQL 不承诺分布式事务：如果本地发布成功而远程失败，会返回错误；重试同一记录版本使用稳定编号，不重复创建远程草稿。本地发布映射供后续撤回使用。数据库错误不会伪装成“没有资料”。

本机命令：

```powershell
.\run.ps1 -Mode admin -Arguments @('shared-check')
.\run.ps1 -Mode admin -Arguments @('import-json','--file','E:/my-notes.json')
.\run.ps1 -Mode admin -Arguments @('review','--record','<本地记录编号>','--version','1','--status','confirmed')
```

import-json 支持 JSON / JSONL、每批最多 100 条 / 10 MB，按一个可见范围原子写入草稿；已有编号不覆盖。默认 private，--shared 才写本地项目区。支持 sources 的 ref 或 uri、结构化 fields 或 CRA 风格顶层字段；引用必须先存在，并使用 research_read 实际返回的编号 / 版本，暂不支持同批次前向引用。

单条普通笔记的输入形状如下；把示例文字替换为真实资料，再保存为 UTF-8 JSON 文件，不把它当成实际研究结论：

```json
{
  "kind": "note",
  "title": "替换为资料标题",
  "body": "替换为原始观察或资料正文",
  "sources": [{"kind": "note", "uri": "urn:local:notes:replace-me"}]
}
```

需要补人工字段时，给 review 增加 --fields-json，文件只放待补字段，例如：

```json
{"adopted": false, "adoption_reason": "填写你实际不采纳的理由"}
```

审核 PostgreSQL 草稿同样使用 review，并给 --record 传 cra: 编号。审核入口只供本机管理员，不注册给模型。已在本地项目区的结构化记录可用 export-shared --record <编号> --version <版本> 明确导出；私有记录必须先明确发布。普通笔记需整理成对应类型并补齐必要字段后才能导出。

## 升级与备份

首次读取旧研究记录 SQLite 会升级至 user_version=2，旧记录默认 draft，原有内容 / 版本保留，不自动审核。正式升级前应使用 SQLite backup 做一致性备份。setup 自动备份的是控制登记库与发生变更的 profile 配置，不等于备份了全部私人库、项目库和 PostgreSQL；历史 .pre-alignment.bak 也不能当作本次最新备份。

数据库持久化与备份需要单独配置，防止服务重建后丢失数据。共享库表结构由 CRA 的迁移维护；禁止在共享业务库执行会删表的降级测试。

本轮不包含：向量服务、PDF / 对象存储、跨项目 PostgreSQL 私有权限、新一轮付费模型效果测试、Linux 真实服务器及微信接入。
