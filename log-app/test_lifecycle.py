import unittest
from unittest.mock import patch
import test_search
import server
import lifecycle

class LifecycleTests(unittest.TestCase):
 setUp=test_search.SearchTests.setUp
 tearDown=test_search.SearchTests.tearDown
 def preview(self,value='active',reason='',identity='Holidays/Italy Trip'):
  return lifecycle.preview(server,{'project':identity,'status':value,'reason':reason})
 def apply(self,value,identity='Holidays/Italy Trip'):
  p=self.preview(value,'A sample reason.',identity)
  return server.save(p['path'],p['content'],p['version'])
 def test_all_states_roundtrip_and_history_reopen(self):
  parent=(server.ROOT/'Holidays/LOG_STATUS.md').read_bytes()
  for value in lifecycle.STATES+('active',):
   self.apply(value)
   project=next(p for p in server.catalog()['projects'] if p['id']=='Holidays/Italy Trip')
   self.assertEqual(project['lifecycle']['value'],value)
   self.assertEqual(project['lifecycle']['reason'],'A sample reason.')
   self.assertIn('Four nights in Rome are confirmed.',self.status.read_text())
  self.assertEqual((server.ROOT/'Holidays/LOG_STATUS.md').read_bytes(),parent)
  self.assertGreaterEqual(len(server.history('Holidays/Italy Trip/LOG_STATUS.md')),6)
 def test_preview_does_not_save_and_preserves_other_sections(self):
  before=self.status.read_bytes();p=self.preview('blocked','Waiting for passport.')
  self.assertEqual(self.status.read_bytes(),before)
  self.assertIn('Four nights in Rome are confirmed.',p['content'])
  self.assertIn('Reason: Waiting for passport.',p['content'])
  self.assertIn('## Recently Updated',p['content']);self.assertIn('+Blocked.',p['diff'])
 def test_stale_preview_cannot_overwrite_external_edit(self):
  p=self.preview();self.status.write_text('External update')
  with self.assertRaises(server.Conflict):server.save(p['path'],p['content'],p['version'])
  self.assertEqual(self.status.read_text(),'External update')
 def test_failed_commit_preserves_previous_state(self):
  before=self.status.read_bytes();p=self.preview('archived');original=server.checkpoint
  def fail(names,message):
   if message.startswith('Update '):raise server.HistoryError('Simulated failure')
   return original(names,message)
  with patch.object(server,'checkpoint',side_effect=fail):
   with self.assertRaises(server.HistoryError):server.save(p['path'],p['content'],p['version'])
  self.assertEqual(self.status.read_bytes(),before)
 def test_archived_parent_does_not_hide_active_child_from_search(self):
  self.apply('archived','Holidays')
  self.assertEqual(lifecycle.state(self.status.read_text())['value'],None)
  r=server.search('Holidays')
  self.assertNotIn('Holidays',[p['id'] for p in r['projects']])
  self.assertIn('Holidays/Italy Trip',[p['id'] for p in server.search('Italy')['projects']])
  self.assertIn('Holidays',[p['id'] for p in server.search('Holidays',True)['projects']])
 def test_archived_files_hidden_and_show_archived_restores_results(self):
  self.apply('archived')
  self.assertEqual(server.search('Four nights')['files'],[])
  self.assertEqual(len(server.search('Four nights',True)['files']),1)
  self.apply('active');self.assertEqual(len(server.search('Four nights')['files']),1)
 def test_validation_unknown_duplicate_and_legacy_status(self):
  self.assertEqual(lifecycle.state('## Lifecycle\n\nActive — early planning.\n')['value'],'active')
  self.assertTrue(lifecycle.state('## Lifecycle\n\nAlmost done.\n')['warning'])
  self.assertTrue(lifecycle.state('## Lifecycle\nActive\n## Lifecycle\nBlocked')['warning'])
  for value in ['deleted',None,'ACTIVE']:
   with self.assertRaises(ValueError):self.preview(value)
  with self.assertRaises(ValueError):self.preview(reason='## Injected heading')
  with self.assertRaises(ValueError):self.preview(identity='../elsewhere')
  self.status.write_text('## Lifecycle\nActive\n## Lifecycle\nBlocked')
  with self.assertRaises(ValueError):self.preview()
 def test_fenced_headings_are_not_rewritten(self):
  text='```md\n## Lifecycle\nExample\n```\n\n## Lifecycle\nActive.\n\n## Notes\nKeep me.\n'
  result=lifecycle.replace_section(text,'Lifecycle','Completed.')
  self.assertIn('## Lifecycle\nExample',result);self.assertIn('## Notes\nKeep me.',result)
  self.assertEqual(lifecycle.state(result)['value'],'completed')
