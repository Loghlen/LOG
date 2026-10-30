"""Search tests use disposable folders and real files, never Desktop files."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib import request, error
import server

class SearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        server.ROOT=Path(self.tmp.name).resolve()
        server.init_history()
        server.create_project('Holidays','Plan holidays','')
        server.create_project('Italy Trip','Plan a relaxed Italy holiday','Holidays')
        self.status=server.ROOT/'Holidays/Italy Trip/LOG_STATUS.md'
        self.status.write_text('# Status\n\n## Summary\n\nFour nights in Rome are confirmed.\n')
    def tearDown(self): self.tmp.cleanup()
    def paths(self,result): return [f['path'] for f in result['files']]

    def test_project_name_phrase_and_owner(self):
        r=server.search('italy trip')
        self.assertEqual([p['id'] for p in r['projects']],['Holidays/Italy Trip'])
        r=server.search('FOUR   nights in rome')
        self.assertEqual(self.paths(r),['Holidays/Italy Trip/LOG_STATUS.md'])
        hit=r['files'][0]
        self.assertEqual((hit['project'],hit['projectName'],hit['matchCount']),('Holidays/Italy Trip','Italy Trip',1))
        self.assertEqual(hit['matches'][0]['line'],5)
        self.assertIn('Four nights in Rome',hit['matches'][0]['text'])
        self.assertEqual(r['query'],'FOUR nights in rome')

    def test_nonexistent_term_gives_explicit_empty_result(self):
        r=server.search('zebra-free phrase')
        self.assertEqual((r['projects'],r['files'],r['truncated']),([],[],False))
        self.assertGreater(r['searchedFiles'],0)

    def test_hidden_git_and_symlinks_are_never_searched(self):
        (server.ROOT/'.private.md').write_text('needle-term\n')
        (server.ROOT/'Real.md').write_text('needle-term\n')
        (server.ROOT/'Alias.md').symlink_to(server.ROOT/'Real.md')
        other=tempfile.TemporaryDirectory();self.addCleanup(other.cleanup)
        outside=Path(other.name);(outside/'secret.md').write_text('needle-term\n')
        (server.ROOT/'linked-folder').symlink_to(outside,target_is_directory=True)
        self.assertEqual(self.paths(server.search('needle-term')),['Real.md'])
        self.assertFalse(any(p.startswith('.git') for p in self.paths(server.search('Initial LOG checkpoint'))))

    def test_unsupported_large_and_unreadable_files_are_reported(self):
        (server.ROOT/'photo.png').write_bytes(b'\x89PNG needle-term')
        (server.ROOT/'bad.md').write_bytes(b'needle-term \xff\xfe')
        (server.ROOT/'big.txt').write_text('needle-term\n'+'x'*server.MAX_FILE)
        r=server.search('needle-term')
        self.assertEqual(r['files'],[])
        reasons={s['path']:s['reason'] for s in r['skipped']}
        self.assertIn('format',reasons['photo.png']);self.assertIn('UTF-8',reasons['bad.md']);self.assertIn('1 MB',reasons['big.txt'])

    def test_json_with_readable_twin_searched_once(self):
        folder=server.ROOT/'Holidays/conversations';folder.mkdir()
        (folder/('a'*32+'.md')).write_text('# Chat\n\nneedle-term\n');(folder/('a'*32+'.json')).write_text('{"x":"needle-term"}')
        (server.ROOT/'data.json').write_text('{"x":"needle-term"}')
        self.assertEqual(self.paths(server.search('needle-term')),['data.json','Holidays/conversations/'+'a'*32+'.md'])

    def test_ordinary_json_twin_keeps_unique_data_searchable(self):
        for relative in ('budget','Holidays/conversations/budget'):
            p=server.ROOT/relative;p.parent.mkdir(exist_ok=True)
            p.with_suffix('.md').write_text('Narrative only.')
            p.with_suffix('.json').write_text('{"value":"jsononlyneedle"}')
        self.assertEqual(set(self.paths(server.search('jsononlyneedle'))),
                         {'budget.json','Holidays/conversations/budget.json'})

    def test_unreadable_generated_twin_does_not_hide_json(self):
        folder=server.ROOT/'Holidays/conversations';folder.mkdir()
        p=folder/('b'*32)
        p.with_suffix('.json').write_text('{"value":"jsononlyneedle"}')
        p.with_suffix('.md').write_bytes(b'\xff')
        self.assertIn(p.with_suffix('.json').relative_to(server.ROOT).as_posix(),self.paths(server.search('jsononlyneedle')))

    def test_unicode_expansion_keeps_match_in_long_snippet(self):
        for prefix,word,query in [('ß'+'x'*900,'targetneedle','targetneedle'),
                                  ('x'*900,'Straße','STRASSE'),
                                  ('ß'*450,'İstanbul','İSTANBUL')]:
            with self.subTest(word=word):
                (server.ROOT/'Unicode.md').write_text(prefix+' '+word+' '+'z'*900)
                hit=server.search(query)['files'][0]['matches'][0]['text']
                self.assertIn(word,hit)
                self.assertLessEqual(len(hit),server.SNIPPET+2)

    def test_control_files_rank_before_documents_and_history(self):
        (server.ROOT/'Notes.md').write_text('needle-term\n')
        folder=server.ROOT/'Holidays/conversations';folder.mkdir();(folder/'b.md').write_text('needle-term\n')
        self.status.write_text('needle-term\n')
        self.assertEqual(self.paths(server.search('needle-term')),
                         ['Holidays/Italy Trip/LOG_STATUS.md','Notes.md','Holidays/conversations/b.md'])

    def test_external_edits_are_found_without_restart(self):
        self.assertEqual(server.search('late addition')['files'],[])
        self.status.write_text(self.status.read_text()+'A late addition.\n')
        self.assertEqual(self.paths(server.search('late addition')),['Holidays/Italy Trip/LOG_STATUS.md'])

    def test_query_validation(self):
        for bad in ('',' ','a','x'*201,None):
            with self.assertRaises(ValueError): server.search(bad)

    def test_line_and_result_limits(self):
        (server.ROOT/'Many.md').write_text('needle-term\n'*12)
        r=server.search('needle-term')
        self.assertEqual((r['files'][0]['matchCount'],len(r['files'][0]['matches'])),(12,server.MAX_LINES_PER_FILE))
        for i in range(4):(server.ROOT/f'File{i}.md').write_text('needle-term\n')
        with patch.object(server,'MAX_RESULTS',3):
            r=server.search('needle-term')
        self.assertTrue(r['truncated']);self.assertLessEqual(sum(max(1,len(f['matches'])) for f in r['files']),3)

    def test_long_lines_are_trimmed_around_the_match(self):
        (server.ROOT/'Long.md').write_text('a'*900+' needle-term '+'b'*900+'\n')
        text=server.search('needle-term')['files'][0]['matches'][0]['text']
        self.assertIn('needle-term',text);self.assertLessEqual(len(text),server.SNIPPET+2)
        self.assertTrue(text.startswith('…') and text.endswith('…'))

    def test_file_name_match_without_content_match(self):
        (server.ROOT/'Budget-ideas.txt').write_text('nothing relevant\n')
        hit=next(f for f in server.search('budget-ideas')['files'] if f['path']=='Budget-ideas.txt')
        self.assertTrue(hit['nameMatch']);self.assertEqual(hit['matchCount'],0)

    def test_http_route_returns_results_and_errors(self):
        quiet=type('QuietHandler',(server.Handler,),{'log_message':lambda *a:None})
        httpd=ThreadingHTTPServer(('127.0.0.1',0),quiet)
        threading.Thread(target=httpd.serve_forever,daemon=True).start()
        self.addCleanup(httpd.server_close);self.addCleanup(httpd.shutdown)
        base=f'http://127.0.0.1:{httpd.server_port}/api/search?q='
        with request.urlopen(base+'four%20nights') as r:
            self.assertEqual(self.paths(json.loads(r.read())),['Holidays/Italy Trip/LOG_STATUS.md'])
        with self.assertRaises(error.HTTPError) as ctx: request.urlopen(base+'a')
        self.assertEqual(ctx.exception.code,400);ctx.exception.close()

if __name__=='__main__': unittest.main()
