"""Meaningful security regressions, using disposable records rather than a new Hermes HOME."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research_ideation.config import Config
from research_ideation.registry import Registry
from research_ideation.context import resolve_context
from research_ideation.models import ResearchError
from research_ideation.storage import Store
from research_ideation import memory,tasks,sharing,knowledge
from research_ideation.adapters.channels import InboundIdentity,resolve_inbound
from research_ideation.adapters.local_files import read_from_inbox
from research_ideation.workflows.daily_update import update


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.registry=Registry(Config.from_root(self.base/"data"));self.registry.initialize()
        self.registry.add_project("persona","人设偏好对齐","研究人设对话领域如何对齐用户偏好","all:persona AND all:preference")
        self.registry.add_project("other","Other","Other research","all:test")
        self.contexts={}
        for user,role in (("alice","owner"),("bob","editor"),("reader","reader"),("service","service")):
            home=self.base/user;home.mkdir();(home/"config.yaml").write_text("{}",encoding="utf-8")
            self.registry.add_user(user,"profile-"+user,home,"service" if user=="service" else "user")
            self.registry.set_member("persona",user,role)
            self.contexts[user]=resolve_context(self.registry,"profile-"+user,home,"persona")
        self.a,self.b,self.service=(self.contexts[k] for k in ("alice","bob","service"))

    def assertCode(self,code,call):
        with self.assertRaises(ResearchError) as error:call()
        self.assertEqual(error.exception.code,code)

    def test_private_snapshot_search_and_guessed_id_do_not_leak(self):
        secret=Store(self.registry,self.a).create("experience","private-token","Only Alice knows this")
        shared=Store(self.registry,self.a).create("problem","Shared problem","Known limitation","project")
        self.assertEqual(Store(self.registry,self.b).list(query="private-token"),[])
        self.assertCode("NOT_FOUND",lambda:Store(self.registry,self.b).get(secret["id"]))
        self.assertNotIn("Only Alice",json.dumps(memory.snapshot(self.registry,self.b)))
        self.assertEqual(Store(self.registry,self.b).get(shared["id"])["title"],"Shared problem")

    def test_profile_binding_spoof_and_membership_revocation(self):
        self.assertCode("IDENTITY_DENIED",lambda:resolve_context(self.registry,self.a.profile,self.b.profile_home,"persona"))
        self.assertCode("ACCESS_DENIED",lambda:resolve_context(self.registry,self.a.profile,self.a.profile_home,"other"))
        self.registry.revoke("persona","alice")
        self.assertCode("ACCESS_DENIED",lambda:Store(self.registry,self.a).list())

    def test_disable_invalidates_existing_execution_context(self):
        self.registry.disable("alice")
        self.assertCode("IDENTITY_DENIED",lambda:memory.snapshot(self.registry,self.a))

    def test_publish_explicit_record_not_whole_chat_and_withdraw(self):
        store=Store(self.registry,self.a)
        selected=store.create("note","share-me","Selected conclusion")
        secret=store.create("note","keep-private","Do not share this")
        published=sharing.publish(self.registry,self.a,selected["id"],1)
        self.assertEqual(sharing.publish(self.registry,self.a,selected["id"],1)["id"],published["id"])
        self.assertEqual(Store(self.registry,self.b).get(published["id"])["body"],"Selected conclusion")
        self.assertCode("NOT_FOUND",lambda:Store(self.registry,self.b).get(secret["id"]))
        sharing.withdraw(self.registry,self.a,published["id"],1)
        self.assertCode("NOT_FOUND",lambda:Store(self.registry,self.b).get(published["id"]))

    def test_private_source_cannot_be_published_via_derived_report(self):
        store=Store(self.registry,self.a)
        secret=store.create("experience","Private source","Private raw fact")
        derived=store.create("note","Derived","A derived conclusion",refs=[{"id":secret["id"],"version":1}])
        self.assertCode("PRIVATE_DERIVATION",lambda:sharing.publish(self.registry,self.a,derived["id"],1))
        self.assertEqual(Store(self.registry,self.b).list(),[])

    def test_readers_and_peer_edits(self):
        reader=self.contexts["reader"]
        self.assertCode("ACCESS_DENIED",lambda:Store(self.registry,reader).create("note","x","y","project"))
        item=Store(self.registry,self.b).create("note","B note","v1","project")
        self.assertCode("ACCESS_DENIED",lambda:Store(self.registry,reader).update(item["id"],1,body="v2"))
        self.assertCode("ACCESS_DENIED",lambda:Store(self.registry,self.b).update(Store(self.registry,self.a).create("note","A note","v1","project")["id"],1,body="v2"))

    def test_optimistic_update_prevents_lost_changes(self):
        store=Store(self.registry,self.a);item=store.create("problem","Problem","v1","project")
        store.update(item["id"],1,body="v2")
        self.assertCode("VERSION_CONFLICT",lambda:store.update(item["id"],1,body="lost update"))
        self.assertEqual(store.get(item["id"])["body"],"v2")

    def test_parallel_contexts_never_share_private_storage(self):
        def operation(ctx):
            store=Store(self.registry,ctx)
            item=store.create("note",ctx.user_id,ctx.user_id+" secret")
            return item["id"],{r["owner_id"] for r in store.list()}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(operation,[self.a,self.b]))
        self.assertEqual(results[0][1],{"alice"});self.assertEqual(results[1][1],{"bob"})

    def test_service_has_no_personal_context(self):
        Store(self.registry,self.a).create("experience","Personal","Secret")
        self.assertNotIn("Secret",json.dumps(memory.snapshot(self.registry,self.service)))
        self.assertCode("ACCESS_DENIED",lambda:Store(self.registry,self.service).create("note","x","y","private"))
        self.assertCode("ACCESS_DENIED",lambda:update(self.registry,self.a))

    def test_channel_requires_verified_namespaced_binding_and_matching_profile(self):
        self.registry.bind("weixin","bot-one","","sender-one","alice")
        identity=InboundIdentity("weixin","bot-one","","sender-one","chat-one",self.a.profile)
        self.assertCode("IDENTITY_DENIED",lambda:resolve_inbound(self.registry,identity))
        self.assertEqual(resolve_inbound(self.registry,identity,True)["user_id"],"alice")
        wrong=InboundIdentity("weixin","bot-two","","sender-one","chat-one",self.a.profile)
        self.assertCode("IDENTITY_DENIED",lambda:resolve_inbound(self.registry,wrong,True))
        wrong=InboundIdentity("weixin","bot-one","","sender-one","chat-one",self.b.profile)
        self.assertCode("IDENTITY_DENIED",lambda:resolve_inbound(self.registry,wrong,True))

    def test_unread_or_fabricated_evidence_cannot_finish(self):
        store=Store(self.registry,self.a)
        paper=store.create("paper","Paper","Original abstract","project")
        task=tasks.start(self.registry,self.a,"How to align preferences?")
        candidate=self.candidate(paper)
        self.assertCode("UNREAD_REFERENCE",lambda:tasks.finish(self.registry,self.a,task["id"],[candidate],"review","local corpus"))
        knowledge.read(self.registry,self.a,paper["id"],task["id"])
        candidate["refs"][0]["quote"]="fabricated quotation"
        self.assertCode("INVALID_REFERENCE",lambda:tasks.finish(self.registry,self.a,task["id"],[candidate],"review","local corpus"))

    def candidate(self,paper):
        return {"title":"Hypothesis","hypothesis":"Testable hypothesis","method":"Specific intervention","related_work":"Difference limited to the checked corpus",
                "experiment":"Baseline, dataset, metric and failure criterion","risks":"Unverified assumptions","refs":[{"id":paper["id"],"version":paper["version"]}]}

    def test_full_workflow_finish_is_idempotent_and_feedback_survives_new_context(self):
        paper=Store(self.registry,self.a).create("paper","Prior work","Real abstract","project")
        task=tasks.start(self.registry,self.a,"Question")
        knowledge.read(self.registry,self.a,paper["id"],task["id"])
        result=tasks.finish(self.registry,self.a,task["id"],[self.candidate(paper)],"Critique","One abstract, no exhaustive novelty proof")
        self.assertEqual(result,tasks.finish(self.registry,self.a,task["id"],[],"ignored","ignored"))
        idea=result["result"]["candidates"][0]["idea_id"]
        tasks.feedback(self.registry,self.a,idea,"rejected","Already tried; data was insufficient.")
        fresh=resolve_context(self.registry,self.a.profile,self.a.profile_home,"persona",session_id="new-session")
        self.assertIn("data was insufficient",json.dumps(memory.snapshot(self.registry,fresh)))
        self.assertCode("NOT_FOUND",lambda:Store(self.registry,self.b).get(idea))

    def test_empty_candidates_are_valid_not_fake_success(self):
        task=tasks.start(self.registry,self.a,"Question")
        result=tasks.finish(self.registry,self.a,task["id"],[],"No evidence","No material available","Need papers")
        self.assertEqual(result["status"],"no_candidate")

    def test_update_failure_retry_dedup_and_service_isolation(self):
        from research_ideation.models import now
        paper={"external_id":"2601.00001v1","url":"https://arxiv.org/abs/2601.00001v1","title":"Persona","abstract":"Abstract","published":now(),"updated":now(),"authors":["Author"]}
        with patch("research_ideation.workflows.daily_update.fetch",side_effect=ResearchError("SOURCE_UNAVAILABLE","offline")):
            self.assertCode("SOURCE_UNAVAILABLE",lambda:update(self.registry,self.service))
        with patch("research_ideation.workflows.daily_update.fetch",return_value=[paper]) as client:
            first=update(self.registry,self.service)
            again=update(self.registry,self.service)
            self.assertEqual(first["new_count"],1);self.assertTrue(again["already_completed"])
            self.assertEqual(client.call_count,1)
            self.assertEqual(update(self.registry,self.service,force=True)["new_count"],0)
        self.assertEqual(len(Store(self.registry,self.b).list(kind="paper")),1)

    def test_local_import_path_traversal_is_rejected(self):
        inbox=self.base/"inbox";inbox.mkdir()
        self.assertCode("INVALID_PATH",lambda:read_from_inbox(inbox,"../alice/config.yaml"))

    def test_historical_evidence_survives_edits_but_not_withdrawal(self):
        store=Store(self.registry,self.a)
        source=store.create("note","Source","Original evidence","project")
        store.update(source["id"],1,body="Revised evidence")
        self.assertEqual(knowledge.read(self.registry,self.b,source["id"],version=1)["body"],"Original evidence")
        self.assertEqual(store.validate_refs([{"id":source["id"],"version":1,"quote":"Original evidence"}],"project")[0]["version"],1)
        store.update(source["id"],2,deleted=1)
        self.assertCode("NOT_FOUND",lambda:store.get_version(source["id"],1))

    def test_shared_task_visible_but_not_editable_by_peer(self):
        task=tasks.start(self.registry,self.service,"Shared question")
        self.assertEqual(tasks.get_task(self.registry,self.b,task["id"])["visibility"],"project")
        self.assertCode("ACCESS_DENIED",lambda:tasks.finish(self.registry,self.b,task["id"],[],"review","scope"))

    def test_withdrawal_cannot_leave_shared_dependency_readable(self):
        store=Store(self.registry,self.a)
        source=store.create("note","Source","Shared evidence","project")
        derived=store.create("note","Derived","Shared result","project",refs=[{"id":source["id"],"version":1}])
        self.assertCode("DEPENDANTS_EXIST",lambda:sharing.withdraw(self.registry,self.a,source["id"],1))
        sharing.withdraw(self.registry,self.a,derived["id"],1)
        sharing.withdraw(self.registry,self.a,source["id"],1)
        self.assertCode("NOT_FOUND",lambda:Store(self.registry,self.b).get(source["id"]))

    def test_shared_task_snapshot_cannot_reveal_withdrawn_memory(self):
        source=Store(self.registry,self.a).create("note","Sensitive shared note","Can be withdrawn","project")
        task=tasks.start(self.registry,self.service,"Question")
        sharing.withdraw(self.registry,self.a,source["id"],1)
        self.assertCode("DEPENDENCY_REVOKED",lambda:tasks.get_task(self.registry,self.b,task["id"]))

    def test_malformed_source_is_not_a_successful_empty_update(self):
        from research_ideation.adapters.arxiv import parse_feed
        self.assertCode("INVALID_FEED",lambda:parse_feed(b'<html>upstream failure</html>'))
        self.assertCode("INVALID_FEED",lambda:parse_feed(b'<broken'))
        self.assertEqual(parse_feed(b'<feed xmlns="http://www.w3.org/2005/Atom"/>'),[])


if __name__=="__main__":unittest.main()
