"""Chat integration tests use mocked OpenAI transport and real local Git."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import server
import chat_service as chat

class ChatTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();server.ROOT=Path(self.tmp.name).resolve();server.init_history()
  server.create_project('Family','Parent context','')
  server.create_project('Italy','Italy context','Family')
  server.create_project('Secret Sibling','Never send me','Family')
  for name in ('read','write','delete'):
   mock=patch.object(chat.credential_store,name,return_value=None);mock.start();self.addCleanup(mock.stop)
  chat.SAVED=False;chat.STORAGE_ERROR=''
  chat.KEY='sk-test-only-not-a-real-key';chat.MODEL=chat.DEFAULT_MODEL
  self.body={'project':'Family/Italy','message':'What is the purpose?','sources':[],'requestId':'a'*32}
 def tearDown(self):
  chat.KEY='';self.tmp.cleanup()
 def response(self):return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'answer':'Plan Italy. [S1]','changes':[]})}]}],'usage':{'input_tokens':100,'output_tokens':8}}
 def test_scoped_answer_and_transcript_no_key(self):
  with patch.object(chat,'api_call',return_value=self.response()) as call:
   result=chat.chat(server,self.body)
  c=result['conversation'];self.assertEqual(c['turns'][0]['status'],'complete')
  payload=call.call_args.args[2]
  self.assertEqual(c['turns'][0]['proposals'],[])
  self.assertEqual(c['turns'][0]['mode'],'auto')
  self.assertFalse(payload['store']);self.assertNotIn('tools',payload)
  self.assertNotIn('Never send me',json.dumps(payload));self.assertNotIn('Parent context',json.dumps(payload))
  self.assertEqual(len(c['turns'][0]['sources']),3)
  transcript=server.ROOT/'Family/Italy/conversations'/f"{c['id']}.md"
  self.assertIn('Plan Italy.',transcript.read_text())
  self.assertNotIn(chat.KEY,transcript.read_text())
  self.assertEqual(len(server.history(transcript.relative_to(server.ROOT).as_posix())),2)
  self.assertEqual(chat.read_conversation(server,'Family/Italy',c['id'])['id'],c['id'])
  with self.assertRaises(FileNotFoundError):chat.read_conversation(server,'Family',c['id'])
 def test_explicit_parent_and_scope_change(self):
  self.body['sources']=['Family/LOG_PROJECT.md']
  with patch.object(chat,'api_call',return_value=self.response()):r=chat.chat(server,self.body)
  c=r['conversation'];self.assertTrue(c['turns'][0]['sources'][-1]['parent'])
  self.body.update(conversation=c['id'],requestId='b'*32,sources=[])
  with self.assertRaises(ValueError):chat.chat(server,self.body)
 def test_reject_sibling_and_traversal_before_transport(self):
  for name in ('Family/Secret Sibling/LOG_PROJECT.md','../outside.md'):
   self.body['sources']=[name]
   with patch.object(chat,'api_call') as call:
    with self.assertRaises(ValueError):chat.chat(server,self.body)
    call.assert_not_called()
 def test_failed_request_saved_and_not_retried(self):
  with patch.object(chat,'api_call',side_effect=chat.ChatError('Connection failed')) as call:
   result=chat.chat(server,self.body);self.assertEqual(call.call_count,1)
  c=result['conversation'];self.assertEqual(c['turns'][0]['status'],'failed')
  self.body['conversation']=c['id']
  with patch.object(chat,'api_call') as call:
   result=chat.chat(server,self.body);self.assertTrue(result['duplicate']);call.assert_not_called()
 def test_no_key_no_files_no_call(self):
  chat.KEY=''
  with patch.object(chat,'api_call') as call:
   with self.assertRaises(chat.ChatError):chat.chat(server,self.body)
   call.assert_not_called()
  self.assertFalse((server.ROOT/'Family/Italy/conversations').exists())
 def test_key_connection_never_returns_secret(self):
  with patch.object(chat,'api_call',return_value={'id':chat.DEFAULT_MODEL}) as call:
   result=chat.connect({'key':'sk-test-not-real-1234567890','model':chat.DEFAULT_MODEL})
  self.assertTrue(result['configured']);self.assertTrue(result['verified'])
  self.assertNotIn('sk-test',json.dumps(result));self.assertEqual(call.call_args.args[0],'/models/'+chat.DEFAULT_MODEL)
  self.assertFalse(chat.disconnect()['configured'])
 def test_context_size_and_pending_busy(self):
  file=server.ROOT/'Family/Italy/Large.md';file.write_text('x'*60001)
  self.body['sources']=['Family/Italy/Large.md']
  with self.assertRaises(ValueError):chat.chat(server,self.body)
  chat.CHAT_LOCK.acquire()
  try:
   with self.assertRaises(server.Conflict):chat.chat(server,self.body)
  finally:chat.CHAT_LOCK.release()
 def test_refusal_and_empty_output(self):
  self.assertEqual(chat.answer_text({'output':[{'type':'message','content':[{'type':'refusal','refusal':'Cannot help.'}]}]}),'Cannot help.')
  with self.assertRaises(chat.ChatError):chat.answer_text({'output':[]})
if __name__=='__main__':unittest.main()
