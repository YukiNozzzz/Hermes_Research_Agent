"""Explicit paid-model acceptance using an existing Hermes runtime, not an emulated agent.

Credentials stay in process; raw transcript is written only to the owning profile's private area.
"""

import argparse
import json
import os
from pathlib import Path
import sys


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-root",required=True)
    parser.add_argument("--data-root",required=True)
    parser.add_argument("--profile",required=True)
    parser.add_argument("--project",default="persona-preference")
    parser.add_argument("--key-file",required=True)
    parser.add_argument("--key-variable",default="LEIHUO_API_KEY")
    parser.add_argument("--model",default="deepseek-flash")
    parser.add_argument("--base-url",default="https://ai.leihuo.netease.com/v1")
    parser.add_argument("--mode",choices=["ideation","overview"],default="ideation")
    args=parser.parse_args()
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from research_ideation.config import Config
    from research_ideation.registry import Registry
    from research_ideation.models import require
    registry=Registry(Config.from_root(args.data_root))
    user=next((u for u in registry.inspect()["users"] if u["profile"]==args.profile),None)
    require(user,"NOT_FOUND","Register a profile before model acceptance.")
    os.environ["HERMES_HOME"]=user["home"]
    os.environ["HERMES_PYTHON_SRC_ROOT"]=args.source_root
    os.environ["HERMES_ENABLE_PROJECT_PLUGINS"]="0"
    sys.path.insert(0,args.source_root)
    from dotenv import dotenv_values
    key=dotenv_values(args.key_file).get(args.key_variable)
    require(key,"KEY_MISSING","The explicitly selected credential variable is not available.")
    os.environ["OPENAI_API_KEY"]=key
    os.environ["OPENAI_BASE_URL"]=args.base_url
    from run_agent import AIAgent
    agent=AIAgent(model=args.model,provider="custom",api_mode="chat_completions",api_key=key,base_url=args.base_url,
                  enabled_toolsets=["research_ideation","skills"],max_iterations=20,max_tokens=4096,run_budget_seconds=240,
                  quiet_mode=True,skip_memory=True,skip_background_review=True,skip_context_files=True,
                  ephemeral_system_prompt="You are accepting a real research plugin. Use real tool results, load the requested skills, preserve personal/project scopes, and answer concisely in Chinese. Never invent records or citations.")
    prompt=f"项目为 {args.project}。先加载 research-ideation:project-assistant，并实际调用 research_project 查询项目。"
    if args.mode=="ideation":
        prompt+=("然后加载 research-ideation:problem-exploration，针对以下问题真实完成一轮并保存："
                 "在人设对话中，当用户偏好与角色设定冲突时，如何在角色一致性和用户满意度之间进行可检验的对齐？"
                 "必须实际调用 research_start，用返回的 task_id 检索并读取论文，评审后调用 research_finish。"
                 "保留至多一个候选，每条参考引用必须来自本轮真实读取的资料。历史实验未提供，不要虚构。"
                 "如果证据不足可以保存零个候选，但仍须调用 finish 记录原因和范围。最后给出任务 ID。")
    else:
        prompt+="请根据真实返回的记录说明项目目标、共享资料与个人记录的区别。只读取，不新增任何记录。"
    try:
        result=agent.run_conversation(prompt)
    finally:
        if callable(getattr(agent,"close",None)):agent.close()
    outputs=[]
    for message in result.get("messages",[]):
        if isinstance(message,dict) and message.get("role")=="tool":
            try:parsed=json.loads(message.get("content",""))
            except (ValueError,TypeError):continue
            outputs.append({"name":message.get("name"),"data":parsed})
    successful=[o["name"] for o in outputs if isinstance(o["data"],dict) and o["data"].get("ok")]
    required={"research_project"} if args.mode=="overview" else {"research_project","research_start","research_search","research_read","research_finish"}
    passed=required<=set(successful) and result.get("completed") is True and not result.get("failed")
    report={"passed":passed,"profile":args.profile,"mode":args.mode,"successful_tools":successful,"final_response":result.get("final_response"),"result":result}
    folder=Path(user["home"])/"plugin-data"/"research-ideation"/"acceptance"
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/(args.mode+".json")
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str).replace(key,"[REDACTED]"),encoding="utf-8")
    print(json.dumps({"passed":passed,"profile":args.profile,"successful_tools":successful,"private_report":str(path)},ensure_ascii=False,indent=2))
    print(result.get("final_response",""))
    if not passed:raise SystemExit(1)


if __name__=="__main__":main()
