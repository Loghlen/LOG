import json
import unittest
from unittest.mock import patch
from datetime import datetime
import test_memory
import test_proposals
import chat_service as chat
import review_records
import server

class ConsistencyTests(unittest.TestCase):
 setUp=test_memory.MemoryTests.setUp
 tearDown=test_memory.MemoryTests.tearDown
 response=test_memory.MemoryTests.response
 review=test_memory.MemoryTests.review
 def test_request_supplies_local_date_and_verified_history(self):
  _,call=self.review([])
  instructions=call.call_args.args[2]['instructions']
  self.assertIn(datetime.now().astimezone().date().isoformat(),instructions)
  self.assertIn('Local Git history enabled: True',instructions)
  self.assertIn('never invent a historical date',instructions)
 def test_stale_history_flagged_even_when_model_misses_it(self):
  p=server.ROOT/'Family/Italy/LOG_PROJECT.md'
  p.write_text(p.read_text()+'\nNo earlier document versions or Git history exist yet.\n')
  r,_=self.review([])
  t=r['conversation']['turns'][0]
  self.assertEqual(t['status'],'complete')
  self.assertIn('Consistency check:',t['answer'])
  self.assertIn('Git history is enabled',t['answer'])
  self.assertEqual(t['proposals'],[])

class ReversalTests(unittest.TestCase):
 setUp=test_proposals.ProposalTests.setUp
 tearDown=test_proposals.ProposalTests.tearDown
 response=test_proposals.ProposalTests.response
 propose=test_proposals.ProposalTests.propose
 def test_reversal_survives_backfill_and_reaches_context_and_readable_record(self):
  c,p,b=self.propose();chat.decide_proposal(server,b)
  c=chat.read_conversation(server,c['project'],c['id'])
  p=c['turns'][0]['proposals'][0]
  p['reversal']={'date':'2026-10-19','commit':'example','reason':'Undone by user'}
  chat.persist(server,c)
  records=review_records.load(server,chat,c['project'])
  r=next(r for r in records if r['id']==p['id'])
  self.assertEqual(r['decision'],'approved')
  self.assertEqual(r['reversal'],p['reversal'])
  docs=chat.sources(server,c['project'],[])
  self.assertIn('Undone by user',review_records.context(records,docs))
  writes=review_records.writes(server,c['project'],records)
  md=next(v.decode() for k,v in writes.items() if k.endswith('.md'))
  self.assertIn('Approved (later reversed)',md)
  self.assertIn('Undone by user',md)
