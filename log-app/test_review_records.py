import json
import unittest
from pathlib import Path
from unittest.mock import patch
import test_proposals
import chat_service as chat
import review_records as records
import server

class ReviewRecordTests(unittest.TestCase):
 setUp=test_proposals.ProposalTests.setUp
 tearDown=test_proposals.ProposalTests.tearDown
 response=test_proposals.ProposalTests.response
 propose=test_proposals.ProposalTests.propose
 def reject(self):
  c,p,b=self.propose();b['decision']='reject';chat.decide_proposal(server,b)
  return c,p,b
 def next_request(self,reconsider=False):
  body={**self.body,'requestId':'b'*32,'reconsiderRejected':reconsider}
  with patch.object(chat,'api_call',return_value=self.response()):r=chat.chat(server,body)
  return r['conversation']['turns'][-1]
 def test_record_is_readable_versioned_and_duplicate_decision_is_idempotent(self):
  c,p,b=self.reject();folder=server.ROOT/'Family/Italy/reviews'
  self.assertTrue((folder/'LOG_REVIEWS.md').exists())
  doc=json.loads((folder/'LOG_REVIEWS.json').read_text())
  self.assertEqual(doc['reviews'][0]['decision'],'rejected')
  self.assertIn(c['id'],(folder/'LOG_REVIEWS.md').read_text())
  head=server.git('rev-parse','HEAD').stdout;chat.decide_proposal(server,b)
  self.assertEqual(server.git('rev-parse','HEAD').stdout,head)
 def test_repeat_rejected_blocked_and_explicit_reconsideration_allowed(self):
  self.reject();t=self.next_request()
  self.assertEqual(t['proposals'],[]);self.assertEqual(len(t['suppressedProposals']),1)
  t=self.next_request(True)
  self.assertEqual(len(t['proposals']),1);self.assertTrue(t['reconsiderRejected'])
 def test_legacy_decisions_backfilled_without_existing_record(self):
  c,p,b=self.reject()
  for f in (server.ROOT/'Family/Italy/reviews').iterdir():f.unlink()
  t=self.next_request();self.assertEqual(t['proposals'],[])
  self.assertTrue((server.ROOT/'Family/Italy/reviews/LOG_REVIEWS.md').exists())
 def test_unrelated_edits_and_bundled_changes_do_not_bypass_rejection(self):
  self.reject();path=server.ROOT/self.name
  path.write_text(self.before+'\nUnrelated new task.\n')
  self.after=path.read_text()+'\n## Budget\n\n£5,000 confirmed by user.\n\nAnother new task.\n'
  self.assertEqual(self.next_request()['proposals'],[])
 def test_other_project_review_not_in_context(self):
  self.reject()
  self.assertEqual(records.load(server,chat,'Family'),[])
 def test_previously_pending_copy_cannot_be_approved_after_rejection(self):
  c,p,b=self.propose()
  self.body['requestId']='c'*32
  c2,p2,b2=self.propose();b2['decision']='reject';chat.decide_proposal(server,b2)
  with self.assertRaises(server.Conflict):chat.decide_proposal(server,b)
  self.assertEqual((server.ROOT/self.name).read_text(),self.before)
 def test_failed_commit_rolls_back_record_and_decision(self):
  c,p,b=self.propose();b['decision']='reject';original=server.checkpoint
  def fail(names,message):
   if message.startswith('Reject '):raise server.HistoryError('Simulated failure')
   return original(names,message)
  with patch.object(server,'checkpoint',side_effect=fail):
   with self.assertRaises(server.HistoryError):chat.decide_proposal(server,b)
  self.assertFalse((server.ROOT/'Family/Italy/reviews/LOG_REVIEWS.json').exists())
  self.assertEqual(chat.read_conversation(server,c['project'],c['id'])['turns'][0]['proposals'][0]['status'],'pending')
