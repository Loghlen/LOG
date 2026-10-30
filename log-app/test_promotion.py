import json
import unittest
import uuid
from unittest.mock import patch
import test_chat
import server
import chat_service as chat

class PromotionTests(unittest.TestCase):
 tearDown=test_chat.ChatTests.tearDown
 def setUp(self):
  test_chat.ChatTests.setUp(self)
  self.status='Family/Italy/LOG_STATUS.md';self.durable='Family/Italy/LOG_PROJECT.md'
  self.original='# Current Status\n\n## Confirmed preference\n- Vegetarian meals. Source: conversation.\n\n## Next actions\n- Compare trains.\n'
  self.clean='# Current Status\n\n## Next actions\n- Compare trains.\n'
  self.memory='# Durable Memory\n\n- Existing fact.\n'
  self.promoted=self.memory+'\n## Confirmed preference\n- Vegetarian meals. Source: conversation.\n'
  for name,value in ((self.status,self.original),(self.durable,self.memory)):
   server.save(name,value,server.file_view(name)['version'])
 def propose(self,dest=None,cleanup=None):
  changes=[{'path':self.status,'reason':'Clean up after promotion','content':self.clean if cleanup is None else cleanup}]
  if dest is not False:changes.append({'path':self.durable,'reason':'Preserve confirmed preference','content':dest or self.promoted})
  response={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'answer':'Review promotion.','changes':changes})}]}]}
  with patch.object(chat,'api_call',return_value=response):r=chat.chat(server,{**self.body,'requestId':uuid.uuid4().hex,'mode':'memory','reviewConversations':[]})
  return r['conversation']
 def decision(self,c,p,decision='approve'):
  return chat.decide_proposal(server,{'project':c['project'],'conversation':c['id'],'proposal':p['id'],'decision':decision})['conversation']
 def prepare(self,c,p):
  return chat.prepare_promotion_cleanup(server,{'project':c['project'],'conversation':c['id'],'proposal':p['id']})
 def test_staged_order_and_exact_preservation_after_two_approvals(self):
  c=self.propose();ps=c['turns'][0]['proposals'];self.assertEqual(len(ps),1);p=ps[0]
  with self.assertRaises(server.Conflict):self.prepare(c,p)
  self.assertEqual((server.ROOT/self.status).read_text(),self.original)
  c=self.decision(c,p)
  self.assertEqual((server.ROOT/self.status).read_text(),self.original)
  r=self.prepare(c,p);cleanup=r['conversation']['turns'][0]['proposals'][-1]
  self.assertEqual(cleanup['status'],'pending')
  self.decision(c,cleanup)
  self.assertEqual((server.ROOT/self.status).read_text(),self.clean)
  self.assertEqual((server.ROOT/self.durable).read_text(),self.promoted)
 def test_rejected_destination_never_allows_cleanup(self):
  c=self.propose();p=c['turns'][0]['proposals'][0];self.decision(c,p,'reject')
  with self.assertRaises(server.Conflict):self.prepare(c,p)
  self.assertEqual((server.ROOT/self.status).read_text(),self.original)
 def test_rejected_cleanup_keeps_both_copies(self):
  c=self.propose();p=c['turns'][0]['proposals'][0];self.decision(c,p)
  r=self.prepare(c,p);cleanup=r['conversation']['turns'][0]['proposals'][-1];self.decision(c,cleanup,'reject')
  self.assertIn('Vegetarian meals',(server.ROOT/self.status).read_text());self.assertIn('Vegetarian meals',(server.ROOT/self.durable).read_text())
 def test_destination_changed_after_prepare_blocks_cleanup(self):
  c=self.propose();p=c['turns'][0]['proposals'][0];self.decision(c,p)
  r=self.prepare(c,p);cleanup=r['conversation']['turns'][0]['proposals'][-1]
  (server.ROOT/self.durable).write_text(self.memory)
  with self.assertRaises(server.Conflict):self.decision(c,cleanup)
  self.assertEqual((server.ROOT/self.status).read_text(),self.original)
 def test_source_changed_blocks_prepare_and_cleanup(self):
  c=self.propose();p=c['turns'][0]['proposals'][0];self.decision(c,p)
  (server.ROOT/self.status).write_text(self.original+'\nNew task.\n')
  with self.assertRaises(server.Conflict):self.prepare(c,p)
 def test_failed_destination_save_leaves_original_and_no_cleanup(self):
  c=self.propose();p=c['turns'][0]['proposals'][0];original=server.checkpoint
  def fail(names,msg):
   if msg.startswith('Approve '):raise server.HistoryError('Simulated failure')
   return original(names,msg)
  with patch.object(server,'checkpoint',side_effect=fail):
   with self.assertRaises(server.HistoryError):self.decision(c,p)
  self.assertEqual((server.ROOT/self.status).read_text(),self.original);self.assertEqual((server.ROOT/self.durable).read_text(),self.memory)
  with self.assertRaises(server.Conflict):self.prepare(c,p)
 def test_failed_cleanup_rolls_back_source_and_keeps_durable(self):
  c=self.propose();p=c['turns'][0]['proposals'][0];self.decision(c,p)
  r=self.prepare(c,p);cleanup=r['conversation']['turns'][0]['proposals'][-1];original=server.checkpoint
  def fail(names,msg):
   if msg.startswith('Approve '):raise server.HistoryError('Simulated failure')
   return original(names,msg)
  with patch.object(server,'checkpoint',side_effect=fail):
   with self.assertRaises(server.HistoryError):self.decision(c,cleanup)
  self.assertEqual((server.ROOT/self.status).read_text(),self.original);self.assertEqual((server.ROOT/self.durable).read_text(),self.promoted)
 def test_destructive_or_paraphrased_promotions_withheld(self):
  c=self.propose(dest=False);self.assertEqual(c['turns'][0]['proposals'],[])
  c=self.propose(dest=self.memory+'\nPrefers vegetarian food.\n')
  self.assertEqual(len(c['turns'][0]['proposals']),1);self.assertNotIn('promotionCleanup',c['turns'][0]['proposals'][0])
 def test_existing_saved_destination_allows_separate_cleanup(self):
  server.save(self.durable,self.promoted,server.file_view(self.durable)['version'])
  c=self.propose(dest=False);p=c['turns'][0]['proposals'][0]
  self.assertIn('promotionDestination',p);self.decision(c,p)
  self.assertEqual((server.ROOT/self.status).read_text(),self.clean)
 def test_prepare_and_approval_are_idempotent_and_survive_reload(self):
  c=self.propose();p=c['turns'][0]['proposals'][0];self.decision(c,p)
  first=self.prepare(c,p);second=self.prepare(c,p);self.assertEqual(first['proposal'],second['proposal'])
  loaded=chat.read_conversation(server,c['project'],c['id']);cleanup=loaded['turns'][0]['proposals'][-1]
  self.decision(c,cleanup);head=server.git('rev-parse','HEAD').stdout
  self.decision(c,cleanup);self.assertEqual(head,server.git('rev-parse','HEAD').stdout)
