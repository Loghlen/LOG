"""Review gate tests: mocked model, real files and Git history."""
import json
import unittest
from unittest.mock import patch
import server
import chat_service as chat
import test_chat

class ProposalTests(unittest.TestCase):
 tearDown=test_chat.ChatTests.tearDown
 def setUp(self):
  test_chat.ChatTests.setUp(self)
  self.name='Family/Italy/LOG_STATUS.md'
  self.before=(server.ROOT/self.name).read_text()
  self.after=self.before+'\n## Budget\n\n£5,000 confirmed by user.\n'
  self.body.update(message='Update our budget to £5,000.')
 def response(self):
  return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'answer':'Please review the budget change.','changes':[{'path':self.name,'reason':'Record your revised budget.','content':self.after}]})}]}]}
 def propose(self):
  with patch.object(chat,'api_call',return_value=self.response()) as call:r=chat.chat(server,self.body)
  self.assertTrue(call.call_args.args[2]['text']['format']['strict'])
  c=r['conversation'];p=c['turns'][-1]['proposals'][0]
  return c,p,{'project':c['project'],'conversation':c['id'],'proposal':p['id'],'decision':'approve'}
 def test_approval_exact_content_persists_and_is_idempotent(self):
  c,p,b=self.propose()
  self.assertEqual((server.ROOT/self.name).read_text(),self.before)
  self.assertIn('+£5,000',p['diff'])
  result=chat.decide_proposal(server,b)
  self.assertEqual((server.ROOT/self.name).read_text(),self.after)
  self.assertEqual(result['conversation']['turns'][-1]['proposals'][0]['status'],'approved')
  head=server.git('rev-parse','HEAD').stdout
  self.assertTrue(chat.decide_proposal(server,b)['duplicate'])
  self.assertEqual(server.git('rev-parse','HEAD').stdout,head)
  names=server.git('diff-tree','--no-commit-id','--name-only','-r','HEAD').stdout.decode()
  self.assertIn(self.name,names);self.assertIn(c['id']+'.json',names)
 def test_reject_never_edits_target(self):
  c,p,b=self.propose();b['decision']='reject'
  chat.decide_proposal(server,b)
  self.assertEqual((server.ROOT/self.name).read_text(),self.before)
  b['decision']='approve'
  with self.assertRaises(server.Conflict):chat.decide_proposal(server,b)
 def test_external_change_blocks_approval_retains_pending(self):
  c,p,b=self.propose();(server.ROOT/self.name).write_text('External update\n')
  with self.assertRaises(server.Conflict):chat.decide_proposal(server,b)
  self.assertEqual((server.ROOT/self.name).read_text(),'External update\n')
  self.assertEqual(chat.read_conversation(server,c['project'],c['id'])['turns'][-1]['proposals'][0]['status'],'pending')
 def test_commit_failure_rolls_back_document_and_review_record(self):
  c,p,b=self.propose();original=server.checkpoint
  def fail(names,message):
   if message.startswith('Approve '):raise server.HistoryError('Simulated disk failure')
   return original(names,message)
  with patch.object(server,'checkpoint',side_effect=fail):
   with self.assertRaises(server.HistoryError):chat.decide_proposal(server,b)
  self.assertEqual((server.ROOT/self.name).read_text(),self.before)
  self.assertEqual(chat.read_conversation(server,c['project'],c['id'])['turns'][-1]['proposals'][0]['status'],'pending')
  self.assertEqual(server.git('diff','--cached','--name-only').stdout,b'')
 def test_scope_incomplete_malformed_empty_and_duplicate_rejected(self):
  docs=chat.sources(server,'Family/Italy',['Family/LOG_STATUS.md'])
  for name in ('Family/LOG_STATUS.md','Family/Secret Sibling/LOG_STATUS.md','../escape.md','Family/Italy/new.md'):
   self.name=name
   with self.assertRaises(chat.ChatError):chat.parse_proposals(server,self.response(),docs)
  self.name='Family/Italy/LOG_STATUS.md'
  r=self.response();r['status']='incomplete'
  with self.assertRaises(chat.ChatError):chat.parse_proposals(server,r,docs)
  self.after=''
  with self.assertRaises(chat.ChatError):chat.parse_proposals(server,self.response(),docs)
 def test_failed_proposal_has_no_approvable_changes(self):
  r=self.response();r['status']='incomplete'
  with patch.object(chat,'api_call',return_value=r):result=chat.chat(server,self.body)
  t=result['conversation']['turns'][-1]
  self.assertEqual(t['status'],'failed');self.assertNotIn('proposals',t)
  self.assertEqual((server.ROOT/self.name).read_text(),self.before)
