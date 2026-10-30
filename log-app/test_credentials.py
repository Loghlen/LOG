import unittest
from unittest.mock import patch
import chat_service as chat
import credential_store as store

class CredentialTests(unittest.TestCase):
 def setUp(self):
  self.old=(chat.KEY,chat.MODEL,chat.VERIFIED,chat.SAVED,chat.STORAGE_ERROR)
  self.addCleanup(self.restore)
 def restore(self):
  chat.KEY,chat.MODEL,chat.VERIFIED,chat.SAVED,chat.STORAGE_ERROR=self.old
 def test_restart_restores_without_network_or_exposing_key(self):
  key='test-credential-not-real-12345'
  with patch.object(store,'read',return_value={'key':key,'model':chat.DEFAULT_MODEL}),patch.object(chat,'api_call') as api:
   state=chat.restore_connection()
  self.assertEqual(chat.KEY,key);self.assertTrue(state['saved']);self.assertNotIn(key,str(state));api.assert_not_called()
 def test_save_failure_preserves_previous_connection(self):
  chat.KEY='previous';chat.SAVED=False
  with patch.object(chat,'api_call'),patch.object(store,'write',side_effect=store.StoreError('Locked')):
   with self.assertRaises(chat.ChatError):chat.connect({'key':'test-credential-not-real-12345'})
  self.assertEqual(chat.KEY,'previous');self.assertFalse(chat.SAVED)
 def test_forget_removes_key_and_blocks_false_success(self):
  chat.KEY='previous';chat.SAVED=True
  with patch.object(store,'delete',side_effect=store.StoreError('Locked')):
   with self.assertRaises(chat.ChatError):chat.disconnect()
  self.assertEqual(chat.KEY,'previous')
  with patch.object(store,'delete') as delete:state=chat.disconnect()
  delete.assert_called_once();self.assertFalse(state['configured']);self.assertFalse(state['saved'])
 def test_locked_keychain_does_not_crash_startup(self):
  chat.KEY='';chat.SAVED=False
  with patch.object(store,'read',side_effect=store.StoreError('Locked')):state=chat.restore_connection()
  self.assertFalse(state['configured']);self.assertEqual(state['storageError'],'Locked')
