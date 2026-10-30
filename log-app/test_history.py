"""Integration tests use real Git in disposable directories, never Desktop files."""
import tempfile
import unittest
from pathlib import Path
import server

class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        server.ROOT=Path(self.tmp.name).resolve()
        self.path=server.ROOT/'Notes.md'
        self.path.write_text('# Original\n')
        server.init_history()
    def tearDown(self): self.tmp.cleanup()
    def test_save_compare_restore_preserves_history(self):
        first=server.history('Notes.md')[0]['id']
        before=server.file_view('Notes.md')
        saved=server.save('Notes.md','# Revised\n',before['version'])
        self.assertEqual(self.path.read_text(),'# Revised\n')
        self.assertEqual(len(server.history('Notes.md')),2)
        diff=server.compare('Notes.md',first,'working')['diff']
        self.assertIn('-# Original',diff); self.assertIn('+# Revised',diff)
        server.save('Notes.md',None,saved['version'],restore=first)
        self.assertEqual(self.path.read_text(),'# Original\n')
        self.assertEqual(len(server.history('Notes.md')),3)
        self.assertEqual(server.revision_bytes('Notes.md',saved['commit']),b'# Revised\n')
    def test_stale_save_and_restore_rejected(self):
        base=server.file_view('Notes.md'); rev=server.history('Notes.md')[0]['id']
        self.path.write_text('External change\n')
        with self.assertRaises(server.Conflict): server.save('Notes.md','Clobber',base['version'])
        with self.assertRaises(server.Conflict): server.save('Notes.md',None,base['version'],restore=rev)
        self.assertEqual(self.path.read_text(),'External change\n')
    def test_external_change_checkpointed(self):
        self.path.write_text('Externally edited\n')
        base=server.file_view('Notes.md')
        server.save('Notes.md','App edit\n',base['version'])
        revisions=server.history('Notes.md')
        self.assertEqual(len(revisions),3)
        self.assertEqual(server.revision_bytes('Notes.md',revisions[1]['id']),b'Externally edited\n')
    def test_new_parent_child_and_duplicate(self):
        p=server.create_project('Holidays','Plan holidays','')
        c=server.create_project('Italy','Plan Italy',p['id'])
        self.assertEqual(c['id'],'Holidays/Italy')
        self.assertEqual(len(list((server.ROOT/c['id']).glob('LOG_*.md'))),3)
        self.assertEqual(server.catalog()['projects'][1]['parent'],'Holidays')
        with self.assertRaises(server.Conflict): server.create_project('Italy','Other',p['id'])
        self.assertEqual(len(server.history(c['id']+'/LOG_README.md')),1)
    def test_traversal_symlinks_bad_revision(self):
        with self.assertRaises(ValueError): server.file_view('../outside.md')
        with self.assertRaises(ValueError): server.file_view('.git/config')
        (server.ROOT/'Alias.md').symlink_to(self.path)
        with self.assertRaises(ValueError): server.file_view('Alias.md')
        with self.assertRaises(ValueError): server.revision_bytes('Notes.md','HEAD')
        with self.assertRaises(ValueError): server.create_project('../Bad','x','')
    def test_staged_changes_block_and_noop(self):
        current=server.file_view('Notes.md')
        self.assertTrue(server.save('Notes.md',current['content'],current['version'])['unchanged'])
        (server.ROOT/'Other.md').write_text('other')
        server.git('add','--','Other.md')
        with self.assertRaises(server.Conflict): server.save('Notes.md','changed',current['version'])
        self.assertEqual(self.path.read_text(),'# Original\n')
    def test_commit_failure_rolls_back(self):
        original=server.git
        def failing(*args,**kwargs):
            if args[0]=='commit': raise server.HistoryError('Simulated failure')
            return original(*args,**kwargs)
        server.git=failing
        try:
            with self.assertRaises(server.HistoryError): server.save('Notes.md','changed',server.file_view('Notes.md')['version'])
        finally: server.git=original
        self.assertEqual(self.path.read_text(),'# Original\n')
        self.assertFalse(server.git('diff','--cached','--name-only').stdout.strip())
if __name__=='__main__': unittest.main()
