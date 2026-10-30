import json
import unittest
from unittest.mock import patch
import test_chat
import server
import chat_service as chat

class MemoryTests(unittest.TestCase):
 tearDown=test_chat.ChatTests.tearDown
 def setUp(self):
  test_chat.ChatTests.setUp(self)
 def response(self,changes=None):
  return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'answer':'Review complete. [S1]','changes':changes or []})}]}]}
 def saved_chat(self,parent=False):
  body=dict(self.body)
  if parent:body['sources']=['Family/LOG_PROJECT.md']
  with patch.object(chat,'api_call',return_value=self.response()):return chat.chat(server,body)['conversation']
 def review(self,ids,changes=None):
  body={**self.body,'mode':'memory','reviewConversations':ids,'requestId':'b'*32}
  with patch.object(chat,'api_call',return_value=self.response(changes)) as call:r=chat.chat(server,body)
  return r,call
 def test_selected_conversation_and_persistent_sources_no_automatic_edits(self):
  c=self.saved_chat();name='Family/Italy/LOG_STATUS.md';before=(server.ROOT/name).read_text()
  result,call=self.review([c['id']],[{'path':name,'reason':'Clarify next steps','content':before+'\nReview options.\n'}])
  t=result['conversation']['turns'][0]
  self.assertEqual(t['status'],'complete');self.assertEqual(len(t['sources']),4)
  self.assertIn(c['id'],json.dumps(call.call_args.args[2]))
  self.assertEqual((server.ROOT/name).read_text(),before)
  self.assertEqual(t['proposals'][0]['status'],'pending')
 def test_unselected_conversations_excluded_and_no_changes_allowed(self):
  c=self.saved_chat();result,call=self.review([])
  self.assertNotIn(c['id'],json.dumps(call.call_args.args[2]))
  self.assertEqual(result['conversation']['turns'][0]['proposals'],[])
 def test_parent_context_cannot_return_through_chat_without_selection(self):
  c=self.saved_chat(parent=True)
  with self.assertRaises(ValueError):self.review([c['id']])
 def test_review_cannot_edit_identity_file(self):
  name='Family/Italy/LOG_README.md';before=(server.ROOT/name).read_text()
  result,_=self.review([],[{'path':name,'reason':'Wrong target','content':before+'\nChanged\n'}])
  t=result['conversation']['turns'][0]
  self.assertEqual(t['status'],'failed');self.assertNotIn('proposals',t)
  self.assertEqual((server.ROOT/name).read_text(),before)
 def test_foreign_conversation_and_limits(self):
  c=self.saved_chat();docs=chat.sources(server,'Family',[])
  with self.assertRaises(FileNotFoundError):chat.memory_sources(server,'Family',[c['id']],docs)
  with self.assertRaises(ValueError):chat.memory_sources(server,'Family/Italy',[c['id']]*6,docs)
  with patch.object(chat,'MAX_HISTORY',1):
   with self.assertRaises(ValueError):chat.memory_sources(server,'Family/Italy',[c['id']],chat.sources(server,'Family/Italy',[]))
 def test_repeat_request_is_idempotent(self):
  first,_=self.review([])
  second,call=self.review([])
  self.assertEqual(first['conversation']['id'],second['conversation']['id']);call.assert_not_called()
